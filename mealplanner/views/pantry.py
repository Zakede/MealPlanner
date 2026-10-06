from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from .. import store, today
from ..costing import price_per_100g, to_grams
from ..db import execute, get_db, query

bp = Blueprint("pantry", __name__, url_prefix="/pantry")

LOCATIONS = ("fridge", "freezer", "shelf")
UNITS = ("g", "ml", "pcs")
MACRO_FIELDS = ("kcal", "protein", "carbs", "fat")


def _num(form, name, default=None):
    raw = (form.get(name) or "").strip()
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number")


def save_food(form, food_id=None):
    """Create or update a food from form fields. Returns the food id.

    A new food with no numbers typed in gets them from the built-in guess table when it knows the food,
    and a blank price is left to the price model, which estimates it from the food's category.
    """
    from ..food_guess import CATEGORIES, guess
    name = (form.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    typed = {m: _num(form, m) for m in MACRO_FIELDS}
    existing = store.food(food_id) if food_id else store.food_by_name(name)
    hint = guess(name) if not existing else None
    if hint and all(v is None for v in typed.values()):
        typed = {m: hint[m] for m in MACRO_FIELDS}
    values = {m: v if v is not None else 0.0 for m, v in typed.items()}
    for m, v in values.items():
        if v < 0 or (m != "kcal" and v > 100) or v > 900:
            raise ValueError(f"{m} per 100 g looks wrong")
    piece_g = _num(form, "piece_g")
    allergens = form.get("allergens")  # None keeps the stored value
    allergens = allergens.strip() if allergens is not None else None
    if hint and not allergens:
        allergens = hint["allergens"]
    ref_price = _num(form, "price_per_100g")
    if ref_price is None and hint:
        ref_price = hint["price_jpy"]
    category = form.get("category") if form.get("category") in CATEGORIES else (hint["category"] if hint else None)

    db = get_db()
    if existing:
        db.execute(
            """UPDATE foods SET name = ?, kcal = ?, protein = ?, carbs = ?, fat = ?,
               piece_g = COALESCE(?, piece_g), allergens = COALESCE(?, allergens),
               price_per_100g = COALESCE(?, price_per_100g), category = COALESCE(?, category) WHERE id = ?""",
            (name, *values.values(), piece_g, allergens, ref_price, category, existing["id"]),
        )
        db.commit()
        return existing["id"]
    cur = db.execute(
        "INSERT INTO foods (name, kcal, protein, carbs, fat, piece_g, allergens, price_per_100g, category)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, *values.values(), piece_g, allergens or "", ref_price, category or ""),
    )
    db.commit()
    return cur.lastrowid


def save_pantry_item(form, item_id=None):
    food_id = save_food(form)
    food = store.food(food_id)
    quantity = _num(form, "quantity")
    if quantity is None or quantity <= 0:
        raise ValueError("quantity must be above zero")
    unit = form.get("unit", "g")
    if unit not in UNITS:
        raise ValueError("unknown unit")
    location = form.get("location", "fridge")
    if location not in LOCATIONS:
        raise ValueError("unknown location")
    expiry = (form.get("expiry") or "").strip() or None
    price_paid = _num(form, "price_paid")
    price_paid = int(round(price_paid)) if price_paid is not None else None
    grams = to_grams(quantity, unit, food["piece_g"])  # raises if pcs without piece weight

    if item_id:
        execute(
            "UPDATE pantry_items SET food_id = ?, quantity = ?, unit = ?, expiry = ?, price_paid = ?,"
            " location = ? WHERE id = ?",
            (food_id, quantity, unit, expiry, price_paid, location, item_id),
        )
    else:
        item_id = execute(
            "INSERT INTO pantry_items (food_id, quantity, unit, expiry, price_paid, location, added_on)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (food_id, quantity, unit, expiry, price_paid, location, today().isoformat()),
        )
    per100 = price_per_100g(price_paid, grams)
    if per100 is not None:
        execute(
            "INSERT INTO price_history (food_id, price_per_100g, recorded_on, source) VALUES (?, ?, ?, 'pantry')",
            (food_id, round(per100, 2), today().isoformat()),
        )
    return item_id


@bp.route("/")
def index():
    items = store.pantry_items(today())
    grouped = {loc: [i for i in items if i["location"] == loc] for loc in LOCATIONS}
    return render_template("pantry/index.html", grouped=grouped)


@bp.route("/new", methods=["GET", "POST"])
@bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
def edit(item_id=None):
    item = None
    if item_id:
        item = next((i for i in store.pantry_items(today()) if i["id"] == item_id), None)
        if item is None:
            abort(404)
    if request.method == "POST":
        try:
            save_pantry_item(request.form, item_id)
        except ValueError as e:
            flash(str(e), "error")
            item = dict(request.form)
        else:
            flash("Saved.", "ok")
            return redirect(url_for("pantry.index"))
    return render_template("pantry/edit.html", item=item or {}, foods=store.foods(),
                           units=UNITS, locations=LOCATIONS, editing=bool(item_id))


@bp.route("/<int:item_id>/delete", methods=["POST"])
def delete(item_id):
    execute("DELETE FROM pantry_items WHERE id = ?", (item_id,))
    flash("Removed.", "ok")
    return redirect(url_for("pantry.index"))


@bp.route("/foods")
def foods():
    return render_template("pantry/foods.html", foods=store.foods())


@bp.route("/foods/new", methods=["GET", "POST"])
@bp.route("/foods/<int:food_id>", methods=["GET", "POST"])
def food_edit(food_id=None):
    food = store.food(food_id) if food_id else {}
    if food_id and not food:
        abort(404)
    if request.method == "POST":
        try:
            save_food(request.form, food_id)
        except ValueError as e:
            flash(str(e), "error")
        else:
            flash("Food saved.", "ok")
            return redirect(url_for("pantry.foods"))
    history = query("SELECT * FROM price_history WHERE food_id = ? ORDER BY recorded_on DESC LIMIT 10",
                    (food_id,)) if food_id else []
    from ..food_guess import CATEGORIES
    return render_template("pantry/food_edit.html", food=food, history=history, categories=CATEGORIES)


@bp.route("/foods/guess")
def food_guess():
    """Numbers for a food name: the built-in table first, then the AI helper if asked and set up."""
    from .. import llm
    from ..food_guess import ai_prompt, guess, validate_ai
    from ..pricing import COUNTRIES, country_code, factor
    name = (request.args.get("name") or "").strip()[:60]
    if not name:
        return jsonify({"error": "Type a name first."}), 400
    s = store.settings()
    found = guess(name)
    if found is None and request.args.get("ai"):
        p = llm.provider()
        if p is None:
            return jsonify({"error": "Not in the built-in list, and no AI helper is set up (Settings → AI helper)."}), 404
        try:
            found = validate_ai(llm.extract_json(p.complete(ai_prompt(name, COUNTRIES[country_code(s)][0]))))
        except llm.LLMError as e:
            return jsonify({"error": f"AI helper: {e}."}), 502
        if found is None:
            return jsonify({"error": "The AI's numbers didn't add up. Try a more specific name."}), 502
    if found is None:
        return jsonify({"error": "Not in the built-in list.", "can_ai": llm.provider() is not None}), 404
    found["price_local"] = round(found["price_jpy"] * factor(s)) if found.get("price_jpy") else None
    return jsonify(found)


@bp.route("/api/foods")
def api_foods():
    return jsonify(store.foods())
