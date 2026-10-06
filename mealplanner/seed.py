"""Starter data for a new database, and library upgrades for an existing one."""
from .library import (BOOSTERS, CRAVING_SWAPS, FOODS, LIBRARY_VERSION, QUICK_PICKS, RECIPES,
                      REMOVED_RECIPES)

# weekday, wake, work_start, work_end, commute, gym, effort, away
SCHEDULE = [
    (0, "07:00", "09:00", "18:00", 40, 1, "low", 0),
    (1, "07:00", "09:00", "18:00", 40, 0, "low", 0),
    (2, "07:00", "09:00", "18:00", 40, 1, "low", 0),
    (3, "07:00", "09:00", "18:00", 40, 0, "low", 0),
    (4, "07:00", "09:00", "18:00", 40, 1, "low", 0),
    (5, "08:30", None, None, 0, 0, "full", 0),
    (6, "08:30", None, None, 0, 0, "full", 0),
]


def _empty(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def _food_ids(conn):
    return {r[1].lower(): r[0] for r in conn.execute("SELECT id, name FROM foods")}


def add_foods(conn):
    """Insert library foods that are missing, and fill in categories for known ones."""
    existing = _food_ids(conn)
    for name, kcal, protein, carbs, fat, price, piece, allergens, category in FOODS:
        if name.lower() in existing:
            conn.execute("UPDATE foods SET category = ? WHERE id = ? AND category = ''",
                         (category, existing[name.lower()]))
        else:
            conn.execute("INSERT INTO foods (name, kcal, protein, carbs, fat, price_per_100g, piece_g, allergens,"
                         " category) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (name, kcal, protein, carbs, fat, price, piece, allergens, category))


def add_recipes(conn):
    food_ids = _food_ids(conn)
    have = {r[0].lower() for r in conn.execute("SELECT name FROM recipes")}
    for (name, active, total, servings, tags, spice, thaw, types, cuisine, batch, portable,
         ingredients, steps) in RECIPES:
        if name.lower() in have:
            conn.execute("UPDATE recipes SET builtin = 1 WHERE name = ?", (name,))
            continue
        cur = conn.execute(
            "INSERT INTO recipes (name, steps, active_min, total_min, servings, tags, spice_level, thaw_hours,"
            " meal_types, cuisine, batch_ok, portable, builtin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (name, steps, active, total, servings, tags, spice, thaw, types, cuisine, batch, portable),
        )
        conn.executemany("INSERT INTO recipe_ingredients (recipe_id, food_id, grams) VALUES (?, ?, ?)",
                         [(cur.lastrowid, food_ids[f.lower()], g) for f, g in ingredients])


def remove_retired_recipes(conn):
    """Drop built-in recipes we no longer ship, unless the user rated or edited around them."""
    for name in REMOVED_RECIPES:
        row = conn.execute("SELECT id FROM recipes WHERE name = ?", (name,)).fetchone()
        if not row:
            continue
        rated = conn.execute("SELECT 1 FROM ratings WHERE recipe_id = ?", (row[0],)).fetchone()
        if not rated:
            conn.execute("DELETE FROM plan_meals WHERE recipe_id = ? AND status IN ('draft', 'approved')", (row[0],))
            conn.execute("DELETE FROM recipes WHERE id = ?", (row[0],))


def add_boosters(conn):
    food_ids = _food_ids(conn)
    have = {r[0] for r in conn.execute("SELECT food_id FROM flavor_boosters")}
    for food, grams, tags, note in BOOSTERS:
        fid = food_ids[food.lower()]
        if fid not in have:
            conn.execute("INSERT INTO flavor_boosters (food_id, grams, tags, note) VALUES (?, ?, ?, ?)",
                         (fid, grams, tags, note))


def add_quick_picks(conn):
    have = {r[0] for r in conn.execute("SELECT item FROM quick_picks")}
    for chain, item, kcal, protein, yen in QUICK_PICKS:
        if item not in have:
            conn.execute("INSERT INTO quick_picks (chain, item, kcal, protein, yen) VALUES (?, ?, ?, ?, ?)",
                         (chain, item, kcal, protein, yen))


def seed(conn):
    if _empty(conn, "settings"):
        conn.execute("INSERT INTO settings (id) VALUES (1)")
    if _empty(conn, "schedule_days"):
        conn.executemany(
            "INSERT INTO schedule_days (weekday, wake, work_start, work_end, commute_min, gym, effort, away)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            SCHEDULE,
        )
    if _empty(conn, "quick_picks"):
        conn.executemany("INSERT INTO quick_picks (chain, item, kcal, protein, yen) VALUES (?, ?, ?, ?, ?)",
                         QUICK_PICKS)
    if _empty(conn, "craving_swaps"):
        conn.executemany("INSERT INTO craving_swaps (craving, swap, kcal_from, kcal_to, note) VALUES (?, ?, ?, ?, ?)",
                         CRAVING_SWAPS)

    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < LIBRARY_VERSION:
        add_foods(conn)
        remove_retired_recipes(conn)
        add_recipes(conn)
        add_boosters(conn)
        add_quick_picks(conn)
        conn.execute(f"PRAGMA user_version = {LIBRARY_VERSION}")
