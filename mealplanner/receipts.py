"""Receipt import: photo or OCR text -> reviewed rows -> pantry items with prices.

The model reads and matches; our code checks every row, and the user reviews before anything is saved.
"""
from datetime import date, timedelta

from . import store
from .costing import price_per_100g
from .db import get_db

# Rough fridge life per food category, used as the default expiry on the review screen.
SHELF_DAYS = {"poultry": 2, "meat": 3, "fish": 2, "seafood": 2, "egg": 14, "dairy": 7, "soy": 5, "legume": 365,
              "grain": 30, "veg": 5, "fruit": 5, "sauce": 180, "fat": 180, "snack": 60}
LOCATION = {"legume": "shelf", "grain": "shelf", "sauce": "shelf", "fat": "shelf", "snack": "shelf"}
MAX_ROWS = 60


def build_prompt(foods):
    names = "\n".join(f"- {f['name']}" for f in foods)
    return f"""Read the attached Japanese grocery receipt photo.

For every bought item (skip totals, tax lines, discounts, bags and points):
- name_ja: the item text as printed
- food: the closest match from the list below, spelled exactly, or null if nothing fits
- grams: your best estimate of the total weight bought (e.g. 10 eggs = 600, 1/2 cabbage = 600, tofu 3P = 450)
- price_yen: the price paid for that line, after any discount on the line below it

Food list:
{names}

Reply with ONE JSON object and nothing else:
{{"store": "...", "date": "YYYY-MM-DD", "total_yen": 0,
  "items": [{{"name_ja": "...", "food": "Chicken breast", "grams": 500, "price_yen": 398}}]}}
"""


def build_match_prompt(items, foods):
    """For receipts that arrive already read (e.g. from another OCR app): only match names."""
    names = "\n".join(f"- {f['name']}" for f in foods)
    lines = "\n".join(f"- {i.get('name_ja') or i.get('name')}: {i.get('quantity') or ''}" for i in items)
    return f"""Match each Japanese grocery item to the closest food in the list, spelled exactly, or null.
Estimate grams bought for each.

Items:
{lines}

Food list:
{names}

Reply with ONE JSON object and nothing else: {{"items": [{{"name_ja": "...", "food": "...", "grams": 0}}]}}
"""


def _int(value, default=0):
    try:
        return int(round(float(str(value).replace(",", "").replace("¥", ""))))
    except (TypeError, ValueError):
        return default


def rows_from_reply(data, today):
    """Turn a model reply into review rows. Returns (rows, header, warnings)."""
    if not isinstance(data, dict):
        return [], {}, ["the reply was not a receipt"]
    warnings = []
    rows = []
    for item in (data.get("items") or [])[:MAX_ROWS]:
        if not isinstance(item, dict):
            continue
        food = store.food_by_name(str(item.get("food") or "")) if item.get("food") else None
        price = max(0, _int(item.get("price_yen")))
        grams = max(0, min(20000, _int(item.get("grams"))))
        category = (food or {}).get("category") or ""
        rows.append({
            "name_ja": str(item.get("name_ja") or item.get("name") or "")[:60],
            "food": food["name"] if food else "",
            "grams": grams or (round(food["piece_g"]) if food and food.get("piece_g") else 0),
            "price": price,
            "expiry": (today + timedelta(days=SHELF_DAYS.get(category, 7))).isoformat(),
            "location": "freezer" if food and "frozen" in food["name"].lower() else LOCATION.get(category, "fridge"),
            "include": bool(food),
        })
    total = _int(data.get("total_yen"))
    lines_sum = sum(r["price"] for r in rows)
    if total and abs(total - lines_sum) > max(50, total * 0.1):
        warnings.append(f"Lines add up to ¥{lines_sum:,} but the receipt total says ¥{total:,}. "
                        "Check for missed items or discounts.")
    unmatched = [r["name_ja"] for r in rows if not r["food"]]
    if unmatched:
        warnings.append("Not matched (left unticked): " + ", ".join(unmatched[:8]))
    try:
        bought = date.fromisoformat(str(data.get("date")))
    except ValueError:
        bought = today
    header = {"store": str(data.get("store") or "")[:60], "date": bought.isoformat(), "total": total}
    return rows, header, warnings


def save_rows(form, today):
    """Add the ticked review rows to the pantry. Returns (added, errors)."""
    db = get_db()
    added, errors = 0, []
    count = _int(form.get("count"))
    for i in range(min(count, MAX_ROWS)):
        if not form.get(f"include_{i}"):
            continue
        name = (form.get(f"food_{i}") or "").strip()
        food = store.food_by_name(name)
        if not food:
            errors.append(f"Row {i + 1}: '{name}' isn't in your food list")
            continue
        grams = _int(form.get(f"grams_{i}"))
        price = _int(form.get(f"price_{i}"))
        if grams <= 0:
            errors.append(f"Row {i + 1}: {name} needs a weight")
            continue
        location = form.get(f"location_{i}") if form.get(f"location_{i}") in ("fridge", "freezer", "shelf") else "fridge"
        expiry = form.get(f"expiry_{i}") or None
        db.execute("INSERT INTO pantry_items (food_id, quantity, unit, expiry, price_paid, location, added_on)"
                   " VALUES (?, ?, 'g', ?, ?, ?, ?)", (food["id"], grams, expiry, price, location, today.isoformat()))
        per100 = price_per_100g(price, grams)
        if per100:
            db.execute("INSERT INTO price_history (food_id, price_per_100g, recorded_on, source) VALUES (?, ?, ?, 'receipt')",
                       (food["id"], round(per100, 2), today.isoformat()))
        added += 1
    db.commit()
    return added, errors
