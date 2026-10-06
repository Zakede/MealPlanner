"""Swap one ingredient for another: chicken breast out, ground beef in.

A swap makes (or reuses) a copy of the recipe with the new ingredient, sized so the protein stays about
the same, then points planned meals at the copy so their calories, protein and cost follow.
"""
import re

from . import store
from .db import get_db, query

PROTEIN_CATEGORIES = {"poultry", "meat", "fish", "seafood", "egg", "soy", "legume"}
MAX_SCALE = 1.6


def main_ingredient(recipe):
    """The ingredient giving the most protein: what you'd usually want to swap."""
    if not recipe["ingredients"]:
        return None
    return max(recipe["ingredients"], key=lambda i: i["protein"] * i["grams"])


def swap_grams(grams, old, new):
    """Same grams, or for protein foods the amount that keeps the protein the same (within limits)."""
    if old.get("category") in PROTEIN_CATEGORIES and new.get("category") in PROTEIN_CATEGORIES \
            and old["protein"] > 0 and new["protein"] > 0:
        scale = max(1 / MAX_SCALE, min(MAX_SCALE, old["protein"] / new["protein"]))
        return round(grams * scale / 5) * 5 or 5
    return grams


def _words(name):
    """Names to look for in titles and steps: 'Chicken breast' -> ['Chicken breast', 'chicken']."""
    first = name.split()[0]
    return [name, first] if first.lower() != name.lower() else [name]


def renamed(text, old_name, new_name):
    for word in _words(old_name):
        pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
        if pattern.search(text):
            def keep_case(m):
                return new_name[:1].upper() + new_name[1:] if m.group(0)[:1].isupper() else new_name.lower()
            return pattern.sub(keep_case, text)
    return text


def variant(recipe_id, old_food_id, new_food_id):
    """Id of a recipe like this one but with new_food in place of old_food (made once, then reused)."""
    recipe = store.recipe(recipe_id, raw=True)
    old, new = store.food(old_food_id), store.food(new_food_id)
    if not recipe or not old or not new:
        raise ValueError("That ingredient or food doesn't exist any more.")
    if old_food_id == new_food_id:
        return recipe_id
    if not any(i["id"] == old_food_id for i in recipe["ingredients"]):
        raise ValueError(f"{recipe['name']} has no {old['name']}.")
    name = renamed(recipe["name"], old["name"], new["name"])
    if name == recipe["name"]:
        name = f"{recipe['name']} with {new['name'].lower()}"
    found = query("SELECT id FROM recipes WHERE name = ?", (name,), one=True)
    if found:
        return found["id"]
    db = get_db()
    row = dict(query("SELECT * FROM recipes WHERE id = ?", (recipe_id,), one=True))
    row.pop("id")
    row.update(name=name, steps=renamed(row["steps"], old["name"], new["name"]), builtin=0)
    cols = list(row)
    cur = db.execute(f"INSERT INTO recipes ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     [row[c] for c in cols])
    new_id = cur.lastrowid
    merged = {}
    for ing in recipe["ingredients"]:
        if ing["id"] == old_food_id:
            merged[new_food_id] = merged.get(new_food_id, 0) + swap_grams(ing["grams"], old, new)
        else:
            merged[ing["id"]] = merged.get(ing["id"], 0) + ing["grams"]
    db.executemany("INSERT INTO recipe_ingredients (recipe_id, food_id, grams) VALUES (?, ?, ?)",
                   [(new_id, fid, g) for fid, g in merged.items()])
    db.commit()
    return new_id


def repoint(meal_ids, recipe_id):
    """Move planned meals (and leftovers cooked with them) onto another recipe, refreshing their numbers.

    Numbers move by the difference between the two recipes, so extras like a flavour booster stay counted.
    """
    from .planner import macros_for
    recipe = store.recipe(recipe_id)
    db = get_db()
    for mid in meal_ids:
        meal = query("SELECT * FROM plan_meals WHERE id = ?", (mid,), one=True)
        if not meal or not meal["recipe_id"]:
            continue
        before = store.recipe(meal["recipe_id"])
        group = [dict(meal)] + [dict(r) for r in query(
            "SELECT * FROM plan_meals WHERE cook_group = ? AND id != ? AND status IN ('draft', 'approved')", (mid, mid))]
        for m in group:
            portion = m["portion"] or 1
            was, now = macros_for(before, portion), macros_for(recipe, portion)
            cost = m["cost"] + (recipe["per_serving"]["cost"] - before["per_serving"]["cost"]) * portion
            db.execute("""UPDATE plan_meals SET recipe_id = ?, title = ?, kcal = ?, protein = ?, carbs = ?, fat = ?,
                          cost = ? WHERE id = ?""",
                       (recipe_id, m["title"].replace(before["name"], recipe["name"]) if before["name"] in m["title"]
                        else recipe["name"],
                        *(round(max(0, m[k] - was[k] + now[k]), 1) for k in ("kcal", "protein", "carbs", "fat")),
                        round(max(0, cost)), m["id"]))
    db.commit()


def swap(meal_id, old_food_id, new_food_id, scope="meal", first=None, last=None):
    """Swap an ingredient in one planned meal, or in every planned meal between first and last that uses it.

    Returns how many meals changed.
    """
    if scope == "week":
        meals = query("""SELECT pm.id, pm.recipe_id FROM plan_meals pm
                         JOIN recipe_ingredients ri ON ri.recipe_id = pm.recipe_id AND ri.food_id = ?
                         WHERE pm.date BETWEEN ? AND ? AND pm.status IN ('draft', 'approved')
                           AND pm.kind != 'leftover'""",
                      (old_food_id, first.isoformat(), last.isoformat()))
    else:
        meals = query("SELECT id, recipe_id FROM plan_meals WHERE id = ?", (meal_id,))
    made = {}
    for m in meals:
        if m["recipe_id"] not in made:
            made[m["recipe_id"]] = variant(m["recipe_id"], old_food_id, new_food_id)
        repoint([m["id"]], made[m["recipe_id"]])
    return len(meals)
