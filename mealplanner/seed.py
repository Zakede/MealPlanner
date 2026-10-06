"""Starter data, inserted only into empty tables."""

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


# name, kcal, protein, carbs, fat (per 100 g), approx. JPY per 100 g, grams per piece, allergens
# Values are approximate Japanese food-table / supermarket figures; edit them to match labels.
FOODS = [
    ("Chicken breast", 105, 23.3, 0, 1.9, 85, None, ""),
    ("Chicken thigh", 127, 19.0, 0, 5.0, 110, None, ""),
    ("Salad chicken", 105, 24.0, 0.5, 1.0, 230, 110, ""),
    ("Pork komagire", 200, 18.5, 0.2, 14.0, 140, None, ""),
    ("Egg", 142, 12.2, 0.4, 10.2, 40, 60, "egg"),
    ("Firm tofu", 73, 7.0, 1.5, 4.9, 30, 300, "soy"),
    ("Natto", 190, 16.5, 12.1, 10.0, 70, 45, "soy"),
    ("Greek yogurt", 60, 10.0, 4.0, 0.4, 140, None, "milk"),
    ("Low-fat milk", 46, 3.8, 5.5, 1.0, 25, None, "milk"),
    ("Protein powder", 390, 75.0, 8.0, 6.0, 300, None, "milk"),
    ("Sliced cheese", 313, 22.7, 1.3, 26.0, 200, 18, "milk"),
    ("Canned mackerel", 174, 20.9, 0.2, 10.7, 110, 190, "fish"),
    ("Canned tuna", 70, 16.0, 0.2, 0.7, 150, 70, "fish"),
    ("Salmon fillet", 124, 22.3, 0.1, 4.1, 250, 100, "fish"),
    ("Frozen shrimp", 82, 18.4, 0.3, 0.6, 250, None, "shrimp"),
    ("Cooked rice", 156, 2.5, 37.1, 0.3, 30, None, ""),
    ("Oats", 380, 13.7, 69.0, 5.7, 70, None, ""),
    ("Bread (shokupan)", 248, 8.9, 46.4, 4.1, 50, 60, "wheat"),
    ("Frozen udon", 95, 2.6, 21.6, 0.4, 40, 200, "wheat"),
    ("Buldak ramen", 379, 8.6, 59.3, 12.1, 180, 140, "wheat, soy, milk"),
    ("Shirataki noodles", 7, 0.2, 3.0, 0.0, 60, 200, ""),
    ("Onion", 37, 1.0, 8.8, 0.1, 40, 200, ""),
    ("Green pepper", 22, 0.9, 5.1, 0.2, 100, 35, ""),
    ("Lettuce", 12, 0.6, 2.8, 0.1, 80, None, ""),
    ("Cabbage", 23, 1.3, 5.2, 0.2, 25, None, ""),
    ("Bean sprouts", 15, 1.7, 2.6, 0.1, 15, 200, ""),
    ("Carrot", 39, 0.7, 9.3, 0.2, 40, 150, ""),
    ("Frozen broccoli", 37, 4.3, 5.2, 0.5, 70, None, ""),
    ("Frozen spinach", 25, 2.9, 3.6, 0.4, 70, None, ""),
    ("Frozen mixed vegetables", 67, 3.0, 13.5, 0.7, 60, None, ""),
    ("Canned tomatoes", 20, 0.9, 4.4, 0.1, 50, 400, ""),
    ("Banana", 86, 1.1, 22.5, 0.2, 40, 100, ""),
    ("Kimchi", 38, 2.3, 5.4, 0.2, 100, None, ""),
    ("Soy sauce", 76, 7.7, 7.9, 0.0, 50, None, "soy, wheat"),
    ("Mirin", 241, 0.3, 43.2, 0.0, 60, None, ""),
    ("Miso", 192, 12.5, 21.9, 6.0, 80, None, "soy"),
    ("Gochujang", 251, 4.9, 54.0, 1.5, 150, None, "soy, wheat"),
    ("Sesame oil", 890, 0.0, 0.0, 100.0, 150, None, "sesame"),
    ("Chili crisp", 600, 3.0, 10.0, 60.0, 300, None, "sesame, soy"),
    ("Garlic", 129, 6.4, 27.5, 0.9, 300, 6, ""),
    ("Curry powder", 338, 13.0, 63.3, 12.2, 800, None, ""),
    ("Rice crackers", 380, 7.0, 85.0, 1.0, 150, None, "soy"),
    ("Light popcorn", 400, 11.0, 70.0, 9.0, 200, None, ""),
]


def _empty(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def seed(conn):
    if _empty(conn, "settings"):
        conn.execute("INSERT INTO settings (id) VALUES (1)")
    if _empty(conn, "schedule_days"):
        conn.executemany(
            "INSERT INTO schedule_days (weekday, wake, work_start, work_end, commute_min, gym, effort, away)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            SCHEDULE,
        )
    if _empty(conn, "foods"):
        conn.executemany(
            "INSERT INTO foods (name, kcal, protein, carbs, fat, price_per_100g, piece_g, allergens)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            FOODS,
        )
