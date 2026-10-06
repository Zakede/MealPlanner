import json
import sqlite3

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from .. import store
from ..db import get_db

bp = Blueprint("recipes", __name__, url_prefix="/recipes")

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")


def _int(form, name, default, lo, hi):
    try:
        value = int(form.get(name, default))
    except (TypeError, ValueError):
        raise ValueError(f"{name.replace('_', ' ')} must be a whole number")
    if not lo <= value <= hi:
        raise ValueError(f"{name.replace('_', ' ')} must be between {lo} and {hi}")
    return value


def parse_recipe(form):
    name = (form.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    values = {
        "name": name,
        "steps": (form.get("steps") or "").strip(),
        "active_min": _int(form, "active_min", 10, 0, 600),
        "total_min": _int(form, "total_min", 15, 0, 1440),
        "servings": _int(form, "servings", 1, 1, 20),
        "spice_level": _int(form, "spice_level", 0, 0, 5),
        "thaw_hours": _int(form, "thaw_hours", 0, 0, 48),
        "fridge_days": _int(form, "fridge_days", 3, 1, 5),
        "tags": ",".join(store.split_list(form.get("tags"))),
        "cuisine": (form.get("cuisine") or "").strip().lower(),
        "meal_types": ",".join(t for t in MEAL_TYPES if form.get(f"type_{t}")) or "lunch,dinner",
        "batch_ok": 1 if form.get("batch_ok") else 0,
        "portable": 1 if form.get("portable") else 0,
    }
    if values["total_min"] < values["active_min"]:
        values["total_min"] = values["active_min"]

    ingredients = []
    for food_name, grams in zip(form.getlist("ing_name"), form.getlist("ing_grams")):
        food_name = food_name.strip()
        if not food_name:
            continue
        food = store.food_by_name(food_name)
        if not food:
            raise ValueError(f"unknown food '{food_name}'. Add it to the food catalogue first")
        try:
            g = float(grams)
        except ValueError:
            raise ValueError(f"grams for {food_name} must be a number")
        if g <= 0:
            raise ValueError(f"grams for {food_name} must be above zero")
        ingredients.append((food["id"], g))
    if not ingredients:
        raise ValueError("add at least one ingredient")
    return values, ingredients


def save_recipe(form, recipe_id=None):
    values, ingredients = parse_recipe(form)
    db = get_db()
    if recipe_id:
        cols = ", ".join(f"{k} = ?" for k in values)
        db.execute(f"UPDATE recipes SET {cols} WHERE id = ?", (*values.values(), recipe_id))
        db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    else:
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        recipe_id = db.execute(f"INSERT INTO recipes ({cols}) VALUES ({marks})", tuple(values.values())).lastrowid
    db.executemany("INSERT INTO recipe_ingredients (recipe_id, food_id, grams) VALUES (?, ?, ?)",
                   [(recipe_id, f, g) for f, g in ingredients])
    db.commit()
    return recipe_id


@bp.route("/")
def index():
    meal_type = request.args.get("type", "")
    items = store.recipes()
    if meal_type in MEAL_TYPES:
        items = [r for r in items if meal_type in r["type_list"]]
    return render_template("recipes/index.html", recipes=items, meal_type=meal_type, meal_types=MEAL_TYPES)


@bp.route("/<int:recipe_id>")
def view(recipe_id):
    r = store.recipe(recipe_id)
    if not r:
        abort(404)
    try:
        portions = max(0.25, min(10.0, float(request.args.get("portions", 1))))
    except ValueError:
        portions = 1.0
    factor = portions / r["servings"]
    return render_template("recipes/view.html", r=r, portions=portions, factor=factor)


@bp.route("/new", methods=["GET", "POST"])
@bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
def edit(recipe_id=None):
    r = store.recipe(recipe_id) if recipe_id else None
    if recipe_id and not r:
        abort(404)
    if request.method == "POST":
        try:
            new_id = save_recipe(request.form, recipe_id)
        except ValueError as e:
            flash(str(e), "error")
        else:
            flash("Recipe saved.", "ok")
            return redirect(url_for("recipes.view", recipe_id=new_id))
    return render_template("recipes/edit.html", r=r, foods=store.foods(), meal_types=MEAL_TYPES)


@bp.route("/<int:recipe_id>/delete", methods=["POST"])
def delete(recipe_id):
    db = get_db()
    db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    db.commit()
    flash("Recipe deleted.", "ok")
    return redirect(url_for("recipes.index"))


@bp.route("/boosters")
def boosters():
    from ..db import query
    rows = query("""SELECT b.*, f.name, f.kcal * b.grams / 100 AS kcal FROM flavor_boosters b
                    JOIN foods f ON f.id = b.food_id ORDER BY f.name""")
    return render_template("recipes/boosters.html", boosters=rows)


@bp.route("/api")
def api():
    return jsonify(store.recipes())


@bp.route("/ai", methods=["GET", "POST"])
def ai():
    from .. import llm, recipe_ai, today
    p = llm.provider()
    if request.method == "GET":
        return render_template("recipes/ai.html", available=p is not None, model=getattr(p, "model", ""))

    request_text = (request.form.get("request") or "").strip()[:300]
    s = store.settings()
    targets = store.targets(s)
    kcal_hint = round(targets.kcal * 0.35) if targets else 600
    protein_hint = round(targets.protein_g * 0.35) if targets else 40
    expiring = [i["name"] for i in store.pantry_items(today())
                if i["days_left"] is not None and 0 <= i["days_left"] <= 3] if request.form.get("use_expiring") else []
    if p is None:
        flash("No recipe model is set up. Install opencode, or set MEALPLANNER_LLM.", "error")
        return redirect(url_for("recipes.ai"))
    try:
        data = llm.extract_json(p.complete(recipe_ai.build_prompt(request_text, store.foods(), s,
                                                                   kcal_hint, protein_hint, expiring)))
    except llm.LLMError as e:
        flash(f"Couldn't get a recipe: {e}. Try again.", "error")
        return redirect(url_for("recipes.ai"))
    recipe, problems, warnings = recipe_ai.validate(data, s)
    return render_template("recipes/ai_preview.html", r=recipe, problems=problems, warnings=warnings,
                           raw=json.dumps(data), request_text=request_text)


@bp.route("/ai/save", methods=["POST"])
def ai_save():
    from werkzeug.datastructures import MultiDict
    from .. import recipe_ai
    try:
        data = json.loads(request.form.get("raw") or "")
    except ValueError:
        data = None
    # check again on save: the page could have been edited
    recipe, problems, _ = recipe_ai.validate(data, store.settings())
    if problems or recipe is None:
        flash("This recipe can't be saved: " + "; ".join(problems or ["invalid data"]), "error")
        return redirect(url_for("recipes.ai"))
    fields, ings = recipe_ai.to_form(recipe)
    form = MultiDict(fields)
    for name, grams in ings:
        form.add("ing_name", name)
        form.add("ing_grams", grams)
    try:
        new_id = save_recipe(form)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("recipes.ai"))
    except sqlite3.IntegrityError:
        flash("A recipe with that name already exists.", "error")
        return redirect(url_for("recipes.ai"))
    flash("Saved. The planner can use it now.", "ok")
    return redirect(url_for("recipes.view", recipe_id=new_id))
