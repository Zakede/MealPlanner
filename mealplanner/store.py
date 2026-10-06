"""Small data-access helpers shared by the views and the planner."""
from .db import query
from .nutrition import activity_multiplier, compute_targets


def week_start():
    """Weeks start on the meal prep day (Sunday if that's one of them), else Monday."""
    try:
        days = {int(x) for x in split_list(settings().get("prep_weekdays")) if x.isdigit()}
    except RuntimeError:  # no app context
        return 0
    return 6 if 6 in days else min(days, default=0)


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
        deficit_kcal=s.get("deficit_kcal") if s.get("goal_mode") == "deficit" else None,
        protein_per_kg=s.get("protein_per_kg") or 1.8,
        fat_share=s.get("fat_share") or 0.25,
    )


def split_list(text):
    return [part.strip().lower() for part in (text or "").split(",") if part.strip()]


# Latest recorded purchase price wins over the catalogue's reference price.
FOOD_SELECT = """
    SELECT f.*,
           (SELECT ph.price_per_100g FROM price_history ph
            WHERE ph.food_id = f.id ORDER BY ph.recorded_on DESC, ph.id DESC LIMIT 1) AS paid_price
    FROM foods f
"""


def price_model():
    """The fitted price model for this request (cached on flask.g)."""
    from flask import g
    s = settings()
    sig = tuple(query("SELECT COUNT(*), MAX(id) FROM price_history", one=True)) +         (s.get("country"), s.get("area"), s.get("shop"), query("SELECT COUNT(*) FROM foods", one=True)[0])
    if g.get("price_model_sig") != sig:
        g.pop("price_model", None)
        g.price_model_sig = sig
    if "price_model" not in g:
        from . import today as get_today
        from .price_model import fit
        from .pricing import COUNTRIES, country_code, factor
        _, _, _, rate, level = COUNTRIES[country_code(s)]
        scale = rate * level
        foods_in = {r["id"]: {"base": r["price_per_100g"] * scale if r["price_per_100g"] is not None else None,
                              "category": r["category"]}
                    for r in query("SELECT id, price_per_100g, category FROM foods")}
        obs = [(r["food_id"], r["price_per_100g"], r["recorded_on"]) for r in query(
            "SELECT food_id, price_per_100g, recorded_on FROM price_history")]
        g.price_model = fit(foods_in, obs, factor(s) / scale if scale else 1.0, get_today())
    return g.price_model


def _priced(row, model):
    """Add current_price: the learned estimate for this food (receipts pull it toward what you pay)."""
    food = dict(row)
    est = model["foods"].get(food["id"], {})
    food["current_price"] = est.get("price")
    food["price_source"] = est.get("source", "estimate")
    food["estimated"] = est.get("source") != "learned"
    food["price_trend"] = est.get("trend")
    return food


def foods():
    m = price_model()
    return [_priced(r, m) for r in query(FOOD_SELECT + " ORDER BY f.name")]


def food(food_id):
    row = query(FOOD_SELECT + " WHERE f.id = ?", (food_id,), one=True)
    return _priced(row, price_model()) if row else None


def food_by_name(name):
    row = query(FOOD_SELECT + " WHERE f.name = ? COLLATE NOCASE", (name.strip(),), one=True)
    return _priced(row, price_model()) if row else None


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


def recipe_ingredients(recipe_id=None, raw=False):
    """Ingredient rows joined with food macros and current price, grouped by recipe id.

    Unless raw, your kitchen staples apply: garlic becomes garlic powder at the right amount, and so on.
    """
    sql = f"""
        SELECT ri.recipe_id, ri.grams, f.* FROM recipe_ingredients ri
        JOIN ({FOOD_SELECT}) f ON f.id = ri.food_id
        {"WHERE ri.recipe_id = ?" if recipe_id else ""}
        ORDER BY ri.id
    """
    grouped = {}
    m = price_model()
    for r in query(sql, (recipe_id,) if recipe_id else ()):
        row = _priced(r, m)
        row["price_per_100g"] = row["current_price"]
        grouped.setdefault(row["recipe_id"], []).append(row)
    if not raw:
        _apply_staples(grouped, m)
    return grouped


def _apply_staples(grouped, model):
    from .staples import load, swap_for
    prefs = load(settings())
    if not any(v.get("use") for v in prefs.values()):
        return
    subs = {}
    for rows in grouped.values():
        for i, row in enumerate(rows):
            swap = swap_for(row["name"], prefs)
            if not swap:
                continue
            name, ratio, note = swap
            if name not in subs:
                found = query(FOOD_SELECT + " WHERE f.name = ? COLLATE NOCASE", (name,), one=True)
                subs[name] = _priced(found, model) if found else None
            sub = subs[name]
            if not sub:
                continue
            new = dict(sub, recipe_id=row["recipe_id"], grams=row["grams"] * ratio,
                       instead_of=row["name"], swap_note=note)
            new["price_per_100g"] = new["current_price"]
            rows[i] = new


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


def recipe(recipe_id, raw=False):
    """A recipe with its numbers. raw=True skips your staple swaps (for editing the recipe itself)."""
    row = query("SELECT * FROM recipes WHERE id = ?", (recipe_id,), one=True)
    if not row:
        return None
    return _with_numbers(row, recipe_ingredients(recipe_id, raw=raw).get(recipe_id, []))


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
