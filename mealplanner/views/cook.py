from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from .. import cooking, store, today
from ..db import execute, query

bp = Blueprint("cook", __name__, url_prefix="/cook")


def get_meal(meal_id):
    row = query("SELECT * FROM plan_meals WHERE id = ?", (meal_id,), one=True)
    if not row:
        abort(404)
    return dict(row)


def missing_note(missing):
    if missing:
        flash("Not in the pantry: " + ", ".join(f"{name} ({g} g)" for name, g in missing)
              + ". Add purchases to keep stock accurate.", "warn")


@bp.route("/<int:meal_id>")
def cook(meal_id):
    meal = get_meal(meal_id)
    if not meal["recipe_id"]:
        return redirect(url_for("plan.week"))
    recipe = store.recipe(meal["recipe_id"])
    cook_portions = meal["cook_portions"] or meal["portion"]
    factor = cook_portions / recipe["servings"]
    plate = meal["portion"] / recipe["servings"]
    steps = [{"text": t.strip(), "timer": cooking.step_timer(t)} for t in recipe["steps"].splitlines() if t.strip()]
    booster = None
    if meal["booster_id"]:
        booster = query("SELECT b.*, f.name FROM flavor_boosters b JOIN foods f ON f.id = b.food_id WHERE b.id = ?",
                        (meal["booster_id"],), one=True)
    from ..swaps import PROTEIN_CATEGORIES, main_ingredient
    main = main_ingredient(recipe)
    foods = sorted(store.foods(), key=lambda f: (f["category"] not in PROTEIN_CATEGORIES, f["name"].lower()))
    return render_template("cook.html", meal=meal, r=recipe, factor=factor, plate=plate,
                           cook_portions=cook_portions, steps=steps, booster=booster,
                           main_id=main["id"] if main else None, swap_foods=foods, protein_cats=PROTEIN_CATEGORIES)


@bp.route("/<int:meal_id>/swap", methods=["POST"])
def swap(meal_id):
    """Swap one ingredient (say chicken for ground beef) in this meal or in the whole week."""
    from .. import plans, swaps
    meal = get_meal(meal_id)
    if meal["status"] not in ("draft", "approved") or not meal["recipe_id"]:
        flash("This meal is already done, so it can't change.", "error")
        return redirect(url_for("cook.cook", meal_id=meal_id))
    try:
        old_id, new_id = int(request.form.get("old_food", 0)), int(request.form.get("new_food", 0))
    except ValueError:
        abort(400)
    scope = "week" if request.form.get("scope") == "week" else "meal"
    from datetime import date as date_cls
    first, last = plans.budget.week_bounds(date_cls.fromisoformat(meal["date"]))
    try:
        changed = swaps.swap(meal_id, old_id, new_id, scope, first, last)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("cook.cook", meal_id=meal_id))
    old, new = store.food(old_id), store.food(new_id)
    if request.form.get("less"):
        execute("INSERT INTO taste_scores (food_id, score) VALUES (?, 'small')"
                " ON CONFLICT(food_id) DO UPDATE SET score = 'small'", (old_id,))
    if query("SELECT 1 FROM shopping_list WHERE week_start = ? LIMIT 1", (first.isoformat(),), one=True):
        plans.build_shopping_list(first)
    extra = " Future plans will use less of it." if request.form.get("less") else ""
    flash(f"{new['name']} in for {old['name'].lower()} in {changed} meal{'s' if changed != 1 else ''}.{extra}", "ok")
    return redirect(url_for("cook.cook", meal_id=meal_id))


@bp.route("/<int:meal_id>/done", methods=["POST"])
def done(meal_id):
    meal = get_meal(meal_id)
    if meal["status"] not in ("draft", "approved"):
        flash("Already logged.", "warn")
        return redirect(url_for("main.home"))
    if meal["kind"] == "cook":
        result = cooking.finish_cooking(meal, freeze=request.form.get("freeze") == "1")
        missing_note(result["missing"])
        if result["leftover_portions"]:
            flash(f"Cooked. {result['leftover_portions']:g} portions saved as leftovers.", "ok")
        else:
            flash("Cooked. Enjoy!", "ok")
    else:
        missing_note(cooking.eat(meal))
        flash("Logged.", "ok")
    # rating screen arrives with taste learning; until then go home
    if meal["recipe_id"] and "cook.rate" in current_app.view_functions:
        return redirect(url_for("cook.rate", meal_id=meal_id))
    return redirect(url_for("main.home"))


@bp.route("/<int:meal_id>/skip", methods=["POST"])
def skip(meal_id):
    n = cooking.skip(get_meal(meal_id))
    extra = n - 1
    msg = "Skipped."
    if extra:
        msg = f"Skipped, along with {extra} leftover meal{'s' if extra > 1 else ''} from it."
    flash(msg + " Undo is on the plan page.", "ok")
    return redirect(request.referrer or url_for("main.home"))


@bp.route("/leftovers")
def leftovers():
    return render_template("leftovers.html", leftovers=cooking.leftovers())


@bp.route("/leftovers/<int:leftover_id>/freeze", methods=["POST"])
def freeze(leftover_id):
    cooking.freeze_leftover(leftover_id)
    flash("Moved to the freezer.", "ok")
    return redirect(url_for("cook.leftovers"))


@bp.route("/leftovers/<int:leftover_id>/discard", methods=["POST"])
def discard(leftover_id):
    cooking.discard_leftover(leftover_id)
    flash("Thrown out.", "ok")
    return redirect(url_for("cook.leftovers"))


QUICK_TAGS = ("loved it", "too spicy", "too bland", "too salty", "loved the crunch", "too much effort", "too small")


@bp.route("/<int:meal_id>/rate", methods=["GET", "POST"])
def rate(meal_id):
    meal = get_meal(meal_id)
    if not meal["recipe_id"]:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        try:
            stars = int(request.form.get("stars", ""))
        except ValueError:
            stars = 0
        if not 1 <= stars <= 5:
            flash("Pick 1 to 5 stars, or tap Skip.", "error")
        else:
            tags = ",".join(t for t in QUICK_TAGS if request.form.get(f"tag_{t}"))
            execute("INSERT INTO ratings (recipe_id, plan_meal_id, stars, tags, rated_on) VALUES (?, ?, ?, ?, ?)",
                    (meal["recipe_id"], meal_id, stars, tags, today().isoformat()))
            flash("Thanks. Future plans will use this.", "ok")
            return redirect(url_for("main.home"))
    return render_template("rate.html", meal=meal, tags=QUICK_TAGS)
