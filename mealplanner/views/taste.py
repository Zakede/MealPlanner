from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import store
from ..db import get_db, query
from ..taste import bayes_stars, insights

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
                           hints=insights(ratings, recipes, s["spice_tolerance"]))
