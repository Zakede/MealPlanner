"""Receipt import: photo or OCR text -> reviewed rows -> pantry items with prices.

The model reads and matches; our code checks every row, and the user reviews before anything is saved.
"""
from datetime import date, timedelta

from . import store
from .food_guess import CATEGORIES, guess, validate_ai
from .costing import price_per_100g
from .db import get_db

# Rough fridge life per food category, used as the default expiry on the review screen.
SHELF_DAYS = {"poultry": 2, "meat": 3, "fish": 2, "seafood": 2, "egg": 14, "dairy": 7, "soy": 5, "legume": 365,
              "grain": 30, "veg": 5, "fruit": 5, "sauce": 180, "fat": 180, "snack": 60}
LOCATION = {"legume": "shelf", "grain": "shelf", "sauce": "shelf", "fat": "shelf", "snack": "shelf"}
MAX_ROWS = 60
KINDS = ("cooking", "snack", "drink", "ready", "other")


def build_prompt(foods):
    names = "\n".join(f"- {f['name']}" for f in foods)
    cats = ", ".join(CATEGORIES)
    return f"""Read the attached Japanese grocery receipt photo.

For every bought item (skip totals, tax lines, discounts, bags and points):
- name_ja: the item text as printed
- name_en: a short plain English name for it. Translate katakana, hiragana and kanji
  (e.g. "ポテトチップス うすしお" -> "Potato chips (lightly salted)", "しめじ" -> "Shimeji mushrooms").
  Drop brand codes and size noise.
- kind: "cooking" (an ingredient for meals), "snack" (chips, sweets, chocolate, ice cream, crackers,
  instant snacks), "drink", "ready" (bento, onigiri, deli food eaten as is) or "other" (not food)
- food: the closest match from the list below, spelled exactly, or null if nothing really fits
  (only match the same food: "Shimeji mushrooms" may match "Mushrooms", but chips never match "Potato")
- grams: your best estimate of the total weight bought (e.g. 10 eggs = 600, 1/2 cabbage = 600, tofu 3P = 450)
- packs: how many packs/pieces were bought (usually 1)
- price_yen: the price paid for that line, after any discount on the line below it
- When food is null and it is food, also give "new_food": per 100 g as sold
  {{"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "category": one of {cats}, "allergens": "comma list"}}

Food list:
{names}

Reply with ONE JSON object and nothing else:
{{"store": "...", "date": "YYYY-MM-DD", "total_yen": 0,
  "items": [{{"name_ja": "...", "name_en": "Chicken breast", "kind": "cooking", "food": "Chicken breast",
             "grams": 500, "packs": 1, "price_yen": 398}}]}}
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
        packs = max(1, min(99, _int(item.get("packs"), 1)))
        name_ja = str(item.get("name_ja") or item.get("name") or "")[:60]
        name_en = " ".join(str(item.get("name_en") or "").split())[:50]
        kind = item.get("kind") if item.get("kind") in KINDS else "cooking"
        new = None
        if not food and kind != "other":
            # not in the food list yet: it becomes a new food when saved, with these numbers
            new = (validate_ai(item["new_food"]) if isinstance(item.get("new_food"), dict) else None) \
                or guess(name_en) or guess(name_ja)
            if new:
                new = {k: new[k] for k in ("kcal", "protein", "carbs", "fat", "category", "allergens") if k in new}
            else:
                new = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "category": "", "allergens": ""}
            if kind == "snack":
                new["category"] = "snack"
        category = (food or {}).get("category") or (new or {}).get("category") or ""
        if kind == "snack" and not category:
            category = "snack"
        name = food["name"] if food else (name_en or name_ja)
        rows.append({
            "name_ja": name_ja,
            "name_en": name_en,
            "kind": kind,
            "food": name if kind != "other" else "",
            "new": new,
            "grams": grams or (round(food["piece_g"]) if food and food.get("piece_g") else 0),
            "packs": packs,
            "price": price,
            "expiry": (today + timedelta(days=SHELF_DAYS.get(category, 7))).isoformat(),
            "location": "freezer" if "frozen" in name.lower() else LOCATION.get(category, "fridge"),
            "include": kind != "other" and bool(name),
        })
    total = _int(data.get("total_yen"))
    lines_sum = sum(r["price"] for r in rows)
    if total and abs(total - lines_sum) > max(50, total * 0.1):
        warnings.append(f"Lines add up to ¥{lines_sum:,} but the receipt total says ¥{total:,}. "
                        "Check for missed items or discounts.")
    skipped = [r["name_ja"] for r in rows if not r["include"]]
    if skipped:
        warnings.append("Not food, left unticked: " + ", ".join(skipped[:8]))
    try:
        bought = date.fromisoformat(str(data.get("date")))
    except ValueError:
        bought = today
    header = {"store": str(data.get("store") or "")[:60], "date": bought.isoformat(), "total": total}
    return rows, header, warnings


def _new_food(name, form, i, kind, grams, packs):
    """Add a food the receipt had that the list didn't, with the numbers read off the receipt (or a guess)."""
    import json
    try:
        nut = json.loads(form.get(f"new_{i}") or "null") or {}
    except ValueError:
        nut = {}
    checked = validate_ai(dict(nut, price_jpy=0)) if nut.get("kcal") is not None else None
    nut = checked or guess(name) or nut
    category = "snack" if kind == "snack" else (nut.get("category") if nut.get("category") in CATEGORIES else "")
    piece = round(grams / packs) if kind == "snack" and grams and packs else None
    get_db().execute(
        "INSERT INTO foods (name, kcal, protein, carbs, fat, piece_g, allergens, price_per_100g, category)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)",
        (name[:50], float(nut.get("kcal") or 0), float(nut.get("protein") or 0), float(nut.get("carbs") or 0),
         float(nut.get("fat") or 0), piece, str(nut.get("allergens") or "")[:80], category))
    return store.food_by_name(name)


def save_rows(form, today):
    """Add the ticked review rows to the pantry, creating foods that aren't in the list yet.

    Returns {"added", "errors", "new_foods", "snacks", "cooking"}.
    """
    db = get_db()
    out = {"added": 0, "errors": [], "new_foods": [], "snacks": 0, "cooking": 0}
    count = _int(form.get("count"))
    for i in range(min(count, MAX_ROWS)):
        if not form.get(f"include_{i}"):
            continue
        name = " ".join((form.get(f"food_{i}") or "").split())[:50]
        kind = form.get(f"kind_{i}") if form.get(f"kind_{i}") in KINDS else "cooking"
        grams = _int(form.get(f"grams_{i}"))
        packs = max(1, _int(form.get(f"packs_{i}"), 1))
        price = _int(form.get(f"price_{i}"))
        if not name:
            out["errors"].append(f"Row {i + 1} needs a name")
            continue
        if grams <= 0:
            out["errors"].append(f"Row {i + 1}: {name} needs a weight")
            continue
        food = store.food_by_name(name)
        if not food:
            food = _new_food(name, form, i, kind, grams, packs)
            out["new_foods"].append(food["name"])
        elif kind == "snack" and not food.get("piece_g"):
            db.execute("UPDATE foods SET piece_g = ? WHERE id = ?", (round(grams / packs), food["id"]))
        location = form.get(f"location_{i}") if form.get(f"location_{i}") in ("fridge", "freezer", "shelf") else "fridge"
        expiry = form.get(f"expiry_{i}") or None
        db.execute("INSERT INTO pantry_items (food_id, quantity, unit, expiry, price_paid, location, added_on)"
                   " VALUES (?, ?, 'g', ?, ?, ?, ?)", (food["id"], grams, expiry, price, location, today.isoformat()))
        per100 = price_per_100g(price, grams)
        if per100:
            db.execute("INSERT INTO price_history (food_id, price_per_100g, recorded_on, source) VALUES (?, ?, ?, 'receipt')",
                       (food["id"], round(per100, 2), today.isoformat()))
            if not food.get("price_per_100g"):
                db.execute("UPDATE foods SET price_per_100g = ? WHERE id = ?", (round(per100, 2), food["id"]))
        out["added"] += 1
        if kind == "snack" or food.get("category") == "snack":
            out["snacks"] += 1
        elif kind == "cooking":
            out["cooking"] += 1
    db.commit()
    return out
