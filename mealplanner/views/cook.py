from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from .. import cooking, store
from ..db import query

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
    return render_template("cook.html", meal=meal, r=recipe, factor=factor, plate=plate,
                           cook_portions=cook_portions, steps=steps, booster=booster)


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
