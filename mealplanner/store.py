"""Small data-access helpers shared by the views and the planner."""
from .db import query
from .nutrition import compute_targets


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
        activity=s["activity"],
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
