"""Small data-access helpers shared by the views and the planner."""
from .db import query
from .nutrition import activity_multiplier, compute_targets


def settings():
    return dict(query("SELECT * FROM settings WHERE id = 1", one=True))


def profile_complete(s):
    return s["age"] is not None and s["sex"] in ("male", "female")


def targets(s=None):
    """Daily targets, or None while age/sex are still missing."""
    s = s or settings()
    if not profile_complete(s):
        return None
    return compute_targets(
        weight_kg=s["weight_kg"],
        height_cm=s["height_cm"],
        age=s["age"],
        sex=s["sex"],
        activity=activity_multiplier(s.get("job", "desk"), s.get("training_days", 3),
                                     s.get("training_intensity", "moderate")),
        pace_kg_week=s["pace_kg_week"],
        goal_weight_kg=s["goal_weight_kg"],
    )


def split_list(text):
    return [part.strip().lower() for part in (text or "").split(",") if part.strip()]


# Latest recorded purchase price wins over the catalogue's reference price.
FOOD_SELECT = """
    SELECT f.*,
           COALESCE((SELECT ph.price_per_100g FROM price_history ph
                     WHERE ph.food_id = f.id ORDER BY ph.recorded_on DESC, ph.id DESC LIMIT 1),
                    f.price_per_100g) AS current_price
    FROM foods f
"""


def foods():
    return [dict(r) for r in query(FOOD_SELECT + " ORDER BY f.name")]


def food(food_id):
    row = query(FOOD_SELECT + " WHERE f.id = ?", (food_id,), one=True)
    return dict(row) if row else None


def food_by_name(name):
    row = query(FOOD_SELECT + " WHERE f.name = ? COLLATE NOCASE", (name.strip(),), one=True)
    return dict(row) if row else None


def pantry_items(today):
    """Pantry rows joined with food data, with grams and days until expiry."""
    from datetime import date
    from .costing import to_grams

    rows = query(
        """SELECT p.*, f.name, f.kcal, f.protein, f.carbs, f.fat, f.piece_g, f.allergens
           FROM pantry_items p JOIN foods f ON f.id = p.food_id
           ORDER BY p.expiry IS NULL, p.expiry, f.name"""
    )
    items = []
    for r in rows:
        item = dict(r)
        try:
            item["grams"] = to_grams(item["quantity"], item["unit"], item["piece_g"])
        except ValueError:
            item["grams"] = None
        item["days_left"] = (date.fromisoformat(item["expiry"]) - today).days if item["expiry"] else None
        items.append(item)
    return items


def recipe_ingredients(recipe_id=None):
    """Ingredient rows joined with food macros and current price, grouped by recipe id."""
    sql = f"""
        SELECT ri.recipe_id, ri.grams, f.* FROM recipe_ingredients ri
        JOIN ({FOOD_SELECT}) f ON f.id = ri.food_id
        {"WHERE ri.recipe_id = ?" if recipe_id else ""}
        ORDER BY ri.id
    """
    grouped = {}
    for r in query(sql, (recipe_id,) if recipe_id else ()):
        row = dict(r)
        row["price_per_100g"] = row["current_price"]
        grouped.setdefault(row["recipe_id"], []).append(row)
    return grouped


def _with_numbers(recipe, ingredients):
    from .costing import per_serving, recipe_totals

    recipe = dict(recipe)
    recipe["ingredients"] = ingredients
    recipe["per_serving"] = per_serving(recipe_totals(ingredients), recipe["servings"])
    recipe["tag_list"] = split_list(recipe["tags"])
    recipe["type_list"] = split_list(recipe["meal_types"])
    recipe["allergens"] = sorted({a for i in ingredients for a in split_list(i["allergens"])})
    return recipe


def recipes():
    ings = recipe_ingredients()
    return [_with_numbers(r, ings.get(r["id"], [])) for r in query("SELECT * FROM recipes ORDER BY name")]


def recipe(recipe_id):
    row = query("SELECT * FROM recipes WHERE id = ?", (recipe_id,), one=True)
    if not row:
        return None
    return _with_numbers(row, recipe_ingredients(recipe_id).get(recipe_id, []))


def recipe_prefs():
    return {r["recipe_id"]: r["status"] for r in query("SELECT * FROM recipe_prefs")}


def set_recipe_pref(recipe_id, status):
    """status: favorite / never / try, or None to clear."""
    from .db import get_db
    db = get_db()
    if status in ("favorite", "never", "try"):
        db.execute("INSERT INTO recipe_prefs (recipe_id, status) VALUES (?, ?)"
                   " ON CONFLICT(recipe_id) DO UPDATE SET status = excluded.status", (recipe_id, status))
    else:
        db.execute("DELETE FROM recipe_prefs WHERE recipe_id = ?", (recipe_id,))
    db.commit()
