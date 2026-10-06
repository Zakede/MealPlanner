from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import store
from ..db import get_db, query
from ..taste import bayes_stars, insights
from .. import food_rules

bp = Blueprint("taste", __name__, url_prefix="/taste")
SCORES = ("like", "small", "dislike")


@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        db = get_db()
        for food in store.foods():
            value = request.form.get(f"f{food['id']}", "")
            if value in SCORES:
                db.execute("INSERT INTO taste_scores (food_id, score) VALUES (?, ?)"
                           " ON CONFLICT(food_id) DO UPDATE SET score = excluded.score", (food["id"], value))
            else:
                db.execute("DELETE FROM taste_scores WHERE food_id = ?", (food["id"],))
        db.commit()
        flash("Saved.", "ok")
        return redirect(url_for("taste.index"))

    scores = {r["food_id"]: r["score"] for r in query("SELECT * FROM taste_scores")}
    ratings = [dict(r) for r in query("SELECT * FROM ratings ORDER BY rated_on DESC, id DESC")]
    recipes = {r["id"]: r for r in store.recipes()}
    per_recipe = {}
    for r in ratings:
        per_recipe.setdefault(r["recipe_id"], []).append(r["stars"])
    ranked = sorted(((recipes[rid]["name"], round(bayes_stars(st), 1), len(st))
                     for rid, st in per_recipe.items() if rid in recipes), key=lambda x: -x[1])
    s = store.settings()
    return render_template("taste.html", foods=store.foods(), scores=scores, ranked=ranked,
                           rules=food_rules.load(s), rule_groups=food_rules.GROUPS, rule_options=food_rules.RULES,
                           diet_now=s.get("diet") or "any",
                           hints=insights(ratings, recipes, s["spice_tolerance"]))


def save_rules(form):
    """Store the protein rules; an air-fryer rule adds the air fryer to your kitchen. Returns meals re-planned."""
    from .. import plans
    from ..db import execute
    rules = food_rules.from_form(form)
    execute("UPDATE settings SET food_rules = ? WHERE id = 1", (food_rules.dump(rules),))
    s = store.settings()
    apps = store.split_list(s.get("appliances"))
    if "airfryer" in rules.values() and "air_fryer" not in apps:
        execute("UPDATE settings SET appliances = ? WHERE id = 1", (",".join(apps + ["air_fryer"]),))
    return plans.refit_for_rules() if store.targets() is not None else 0


@bp.route("/rules", methods=["POST"])
def rules():
    changed = save_rules(request.form)
    flash("Saved." + (f" {changed} meal{'s' if changed != 1 else ''} re-planned to match." if changed else ""), "ok")
    return redirect(url_for("taste.index"))
