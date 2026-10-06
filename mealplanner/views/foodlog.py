from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import llm, logbook, store, today
from ..db import execute, query
from ..pricing import currency

bp = Blueprint("foodlog", __name__, url_prefix="/log")
SLOTS = ("breakfast", "lunch", "dinner", "snack")


def _num(form, key, lo, hi, default=0.0):
    try:
        return max(lo, min(hi, float(form.get(key) or default)))
    except ValueError:
        return default


def estimate_prompt(text, cur):
    return f"""Estimate the nutrition of one serving of this food someone ate, as sold or served:
"{text[:200]}"

Use typical Japanese konbini / restaurant / home portions when that fits. Be realistic, not optimistic.
Reply with ONE JSON object and nothing else:
{{"name": "short clear name", "kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "price": 0, "confidence": "low|medium|high"}}
price is the usual price in {cur} (0 if homemade or unknown).
"""


def check_estimate(data):
    """Keep only sane numbers from a model's guess."""
    if not isinstance(data, dict):
        return None
    try:
        kcal = float(data.get("kcal"))
    except (TypeError, ValueError):
        return None
    if not 0 < kcal <= 3000:
        return None
    out = {"name": str(data.get("name") or "Food")[:60], "kcal": round(kcal)}
    for key, hi in (("protein", 200), ("carbs", 400), ("fat", 200), ("price", 100000)):
        try:
            out[key] = max(0, min(hi, round(float(data.get(key) or 0), 1)))
        except (TypeError, ValueError):
            out[key] = 0
    # macros can't add up to far more calories than the total
    if out["protein"] * 4 + out["carbs"] * 4 + out["fat"] * 9 > kcal * 1.4:
        out.update(protein=0, carbs=0, fat=0)
    out["confidence"] = data.get("confidence") if data.get("confidence") in ("low", "medium", "high") else "low"
    return out


def guess_slot():
    from ..plans import now_minutes
    now = now_minutes()
    if now < 10 * 60:
        return "breakfast"
    if 11 * 60 <= now < 14 * 60:
        return "lunch"
    if 17 * 60 + 30 <= now < 21 * 60:
        return "dinner"
    return "snack"


def done(notes, name, kcal):
    flash(f"Logged {name}, {kcal} kcal. " + " ".join(notes), "ok")
    return redirect(request.form.get("back") or url_for("main.home"))


@bp.route("/")
def page():
    picks = [dict(r) for r in query("SELECT * FROM quick_picks ORDER BY chain, item")]
    return render_template("log.html", picks=picks, foods=store.foods(), recipes=store.recipes(),
                           today_log=logbook.food_today(today()), slots=SLOTS, slot=guess_slot(),
                           tab=request.args.get("tab", "picks"), estimate=None, ai=llm.provider() is not None)


@bp.route("/pick/<int:pick_id>", methods=["POST"])
def pick(pick_id):
    p = query("SELECT * FROM quick_picks WHERE id = ?", (pick_id,), one=True)
    if not p:
        return redirect(url_for("foodlog.page"))
    slot = request.form.get("slot") if request.form.get("slot") in SLOTS else guess_slot()
    notes = logbook.log_food(today(), p["item"], p["kcal"], p["protein"], yen=p["yen"], slot=slot, source=p["chain"])
    return done(notes, p["item"], p["kcal"])


@bp.route("/add", methods=["POST"])
def add():
    f = request.form
    slot = f.get("slot") if f.get("slot") in SLOTS else guess_slot()
    mode = f.get("mode", "manual")
    if mode == "food":
        food = store.food_by_name(f.get("food", ""))
        grams = _num(f, "grams", 0, 3000)
        if not food or grams <= 0:
            flash("Pick a food from the list and how many grams.", "error")
            return redirect(url_for("foodlog.page", tab="mine"))
        k = grams / 100
        name = f"{food['name']} {grams:g} g"
        values = dict(kcal=food["kcal"] * k, protein=food["protein"] * k, carbs=food["carbs"] * k, fat=food["fat"] * k,
                      yen=(food["current_price"] or 0) * k if f.get("bought") else 0)
    elif mode == "recipe":
        r = store.recipe(int(_num(f, "recipe_id", 0, 10 ** 9)))
        portions = _num(f, "portions", 0.25, 4, 1)
        if not r:
            flash("Pick a recipe.", "error")
            return redirect(url_for("foodlog.page", tab="mine"))
        s = r["per_serving"]
        name = r["name"] + (f" ×{portions:g}" if portions != 1 else "")
        values = dict(kcal=s["kcal"] * portions, protein=s["protein"] * portions, carbs=s["carbs"] * portions,
                      fat=s["fat"] * portions, yen=0)
    else:
        name = (f.get("name") or "").strip()
        kcal = _num(f, "kcal", 0, 4000)
        if not name or kcal <= 0:
            flash("Give it a name and the calories (a guess is fine).", "error")
            return redirect(url_for("foodlog.page", tab="type"))
        values = dict(kcal=kcal, protein=_num(f, "protein", 0, 300), carbs=_num(f, "carbs", 0, 500),
                      fat=_num(f, "fat", 0, 300), yen=_num(f, "yen", 0, 100000))
    kcal = round(values.pop("kcal"))
    notes = logbook.log_food(today(), name, kcal, slot=slot, source=mode,
                             **{k: round(v, 1) if k != "yen" else round(v) for k, v in values.items()})
    return done(notes, name, kcal)


@bp.route("/estimate", methods=["POST"])
def estimate():
    text = (request.form.get("text") or "").strip()
    p = llm.provider()
    est = None
    if not text:
        flash("Type what you ate, like \"7-11 curry pan\".", "error")
    elif p is None:
        flash("Add a Gemini key in Settings to use estimates, or type the numbers yourself.", "error")
    else:
        try:
            est = check_estimate(llm.extract_json(p.complete(estimate_prompt(text, currency(store.settings())))))
            if not est:
                flash("That estimate didn't look right. Type the numbers instead.", "error")
        except llm.LLMError as e:
            flash(f"Couldn't estimate: {e}.", "error")
    picks = [dict(r) for r in query("SELECT * FROM quick_picks ORDER BY chain, item")]
    return render_template("log.html", picks=picks, foods=store.foods(), recipes=store.recipes(),
                           today_log=logbook.food_today(today()), slots=SLOTS, slot=guess_slot(),
                           tab="type", estimate=est, asked=text, ai=p is not None)


@bp.route("/<int:entry_id>/delete", methods=["POST"])
def delete(entry_id):
    execute("DELETE FROM food_log WHERE id = ?", (entry_id,))
    flash("Removed.", "ok")
    return redirect(request.referrer or url_for("foodlog.page"))
