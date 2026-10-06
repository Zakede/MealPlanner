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


# name, active_min, total_min, servings, tags, spice, thaw_hours, meal_types, cuisine, batch_ok, portable,
# ingredients [(food, grams for the whole recipe)], steps
RECIPES = [
    ("Buldak noodles with onion, green pepper & lettuce", 10, 12, 1, "spicy,flavor-first,crunchy", 4, 0,
     "lunch,dinner", "korean", 0, 0,
     [("Buldak ramen", 140), ("Onion", 60), ("Green pepper", 35), ("Lettuce", 40)],
     "Slice the onion and green pepper thinly. Shred the lettuce.\n"
     "Boil the noodles for 5 minutes, adding the onion and pepper for the last minute.\n"
     "Drain, leaving about 8 tablespoons of water in the pot.\n"
     "Stir in the sauce over low heat for 30 seconds.\n"
     "Top with the lettuce for crunch."),
    ("Buldak chicken & cabbage bowl", 15, 18, 1, "spicy,flavor-first", 4, 0,
     "lunch,dinner", "korean", 0, 0,
     [("Buldak ramen", 70), ("Chicken breast", 150), ("Cabbage", 120), ("Onion", 40)],
     "Slice the chicken thinly and fry until cooked through, about 5 minutes.\n"
     "Boil half a pack of noodles with the cabbage and onion for 4 minutes.\n"
     "Drain, toss everything with half the sauce packet."),
    ("Chicken teriyaki rice bowl", 15, 20, 1, "sweet-savory", 0, 0,
     "lunch,dinner", "japanese", 0, 1,
     [("Chicken breast", 150), ("Cooked rice", 180), ("Soy sauce", 15), ("Mirin", 15), ("Frozen broccoli", 80)],
     "Cut the chicken into bite-size pieces.\n"
     "Fry on medium-high until browned and cooked through, about 6 minutes.\n"
     "Add soy sauce and mirin, reduce until glossy.\n"
     "Microwave the broccoli for 2 minutes. Serve over rice."),
    ("Natto egg rice with kimchi", 3, 3, 1, "savory,quick", 1, 0,
     "breakfast,lunch", "japanese", 0, 0,
     [("Cooked rice", 150), ("Natto", 45), ("Egg", 60), ("Kimchi", 40), ("Soy sauce", 5)],
     "Warm the rice.\n"
     "Stir the natto with its sauce, then top the rice with natto, a raw or soft-boiled egg and kimchi."),
    ("Pork & tofu kimchi stir-fry", 15, 15, 1, "spicy,garlicky", 2, 0,
     "lunch,dinner", "korean", 0, 0,
     [("Pork komagire", 100), ("Firm tofu", 150), ("Kimchi", 80), ("Onion", 50), ("Bean sprouts", 100),
      ("Sesame oil", 5), ("Gochujang", 10)],
     "Cube the tofu and slice the onion.\n"
     "Fry the pork in sesame oil on high heat until no pink is left, about 3 minutes.\n"
     "Add onion and kimchi, fry 2 minutes.\n"
     "Add bean sprouts, tofu and gochujang, toss gently for 2 minutes."),
    ("Saba rice bowl with cabbage", 5, 5, 1, "savory,quick", 0, 0,
     "lunch,dinner", "japanese", 0, 1,
     [("Canned mackerel", 100), ("Cooked rice", 150), ("Cabbage", 80), ("Soy sauce", 5)],
     "Shred the cabbage.\n"
     "Flake the mackerel over warm rice with the cabbage and a splash of soy sauce."),
    ("Greek yogurt oat bowl", 2, 2, 1, "sweet", 0, 0,
     "breakfast", "", 0, 1,
     [("Greek yogurt", 200), ("Oats", 40), ("Banana", 100)],
     "Spoon yogurt into a bowl, top with oats and sliced banana."),
    ("Protein overnight oats", 3, 3, 1, "sweet", 0, 0,
     "breakfast", "", 0, 1,
     [("Oats", 50), ("Low-fat milk", 200), ("Protein powder", 30)],
     "Mix everything in a jar the night before and keep it in the fridge."),
    ("Egg & cheese toast", 8, 8, 1, "cheesy", 0, 0,
     "breakfast", "", 0, 0,
     [("Bread (shokupan)", 60), ("Egg", 120), ("Sliced cheese", 18), ("Lettuce", 20)],
     "Scramble the eggs.\n"
     "Toast the bread with the cheese on top, then add lettuce and eggs."),
    ("Oyakodon", 15, 20, 1, "sweet-savory", 0, 0,
     "lunch,dinner", "japanese", 0, 0,
     [("Chicken thigh", 120), ("Egg", 120), ("Onion", 60), ("Cooked rice", 180), ("Soy sauce", 15), ("Mirin", 15)],
     "Simmer sliced onion in soy sauce, mirin and 60 ml water for 3 minutes.\n"
     "Add the chicken and simmer until cooked through, about 6 minutes.\n"
     "Pour in beaten eggs, cover for 1 minute, and slide over rice."),
    ("Chicken & egg udon", 10, 12, 1, "savory", 0, 0,
     "lunch,dinner", "japanese", 0, 0,
     [("Frozen udon", 200), ("Chicken breast", 100), ("Egg", 60), ("Soy sauce", 15), ("Mirin", 10),
      ("Frozen spinach", 50)],
     "Bring 350 ml water with soy sauce and mirin to a simmer.\n"
     "Add sliced chicken, cook 5 minutes.\n"
     "Add udon and spinach, crack in the egg, cook 2 minutes."),
    ("Chicken & vegetable curry (batch)", 25, 50, 4, "spicy,garlicky", 2, 0,
     "lunch,dinner", "japanese", 1, 1,
     [("Chicken breast", 600), ("Onion", 200), ("Carrot", 150), ("Frozen broccoli", 200),
      ("Canned tomatoes", 400), ("Curry powder", 15), ("Garlic", 12), ("Cooked rice", 720)],
     "Dice the onion, carrot and chicken. Crush the garlic.\n"
     "Soften the onion and garlic in a dry non-stick pot, about 5 minutes.\n"
     "Add chicken and curry powder, cook 3 minutes.\n"
     "Add tomatoes, carrot and 200 ml water, simmer 25 minutes.\n"
     "Add broccoli for the last 5 minutes. Cool quickly and refrigerate portions within an hour."),
    ("Garlic shrimp fried rice", 15, 20, 2, "garlicky", 0, 12,
     "lunch,dinner", "chinese", 1, 1,
     [("Frozen shrimp", 200), ("Cooked rice", 300), ("Egg", 120), ("Frozen mixed vegetables", 150),
      ("Soy sauce", 15), ("Sesame oil", 5), ("Garlic", 6)],
     "Thaw the shrimp in the fridge overnight.\n"
     "Scramble the eggs in sesame oil and set aside.\n"
     "Fry garlic and shrimp until pink, about 3 minutes.\n"
     "Add vegetables and rice, fry 4 minutes, then the eggs and soy sauce."),
    ("Salmon, tofu & miso soup set", 15, 20, 1, "savory", 0, 0,
     "dinner", "japanese", 0, 0,
     [("Salmon fillet", 120), ("Miso", 15), ("Firm tofu", 100), ("Frozen spinach", 50), ("Cooked rice", 150)],
     "Grill the salmon 8-10 minutes until it flakes.\n"
     "Simmer tofu and spinach in 300 ml water, then dissolve the miso off the heat.\n"
     "Serve with rice."),
    ("Salad chicken", 0, 0, 1, "quick", 0, 0, "snack", "", 0, 1,
     [("Salad chicken", 110)], "Open and eat."),
    ("Boiled eggs", 2, 12, 1, "quick", 0, 0, "snack,breakfast", "", 1, 1,
     [("Egg", 120)], "Boil for 8 minutes, cool in cold water, peel."),
    ("Greek yogurt cup", 0, 0, 1, "sweet", 0, 0, "snack", "", 0, 1,
     [("Greek yogurt", 150)], "Eat as is, or add cinnamon."),
    ("Rice crackers", 0, 0, 1, "crunchy", 0, 0, "snack", "japanese", 0, 1,
     [("Rice crackers", 30)], "Portion 30 g into a bowl rather than eating from the bag."),
    ("Light popcorn", 0, 0, 1, "crunchy", 0, 0, "snack", "", 0, 1,
     [("Light popcorn", 25)], "Portion 25 g. Season with chili powder or nori if you like."),
]

# food, grams, tags, note
BOOSTERS = [
    ("Kimchi", 50, "spicy,sour", "Adds crunch and heat for about 20 kcal"),
    ("Soy sauce", 10, "savory", "Salty depth for under 10 kcal"),
    ("Sesame oil", 3, "nutty", "A few drops go a long way (27 kcal)"),
    ("Chili crisp", 8, "spicy,crunchy", "Big flavour, about 50 kcal"),
    ("Gochujang", 10, "spicy,sweet-savory", "Sweet heat for 25 kcal"),
    ("Garlic", 6, "garlicky", "One clove, almost no calories"),
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
    if _empty(conn, "recipes"):
        food_ids = {r[1].lower(): r[0] for r in conn.execute("SELECT id, name FROM foods")}
        for (name, active, total, servings, tags, spice, thaw, types, cuisine, batch, portable,
             ingredients, steps) in RECIPES:
            cur = conn.execute(
                "INSERT INTO recipes (name, steps, active_min, total_min, servings, tags, spice_level, thaw_hours,"
                " meal_types, cuisine, batch_ok, portable) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, steps, active, total, servings, tags, spice, thaw, types, cuisine, batch, portable),
            )
            conn.executemany(
                "INSERT INTO recipe_ingredients (recipe_id, food_id, grams) VALUES (?, ?, ?)",
                [(cur.lastrowid, food_ids[f.lower()], g) for f, g in ingredients],
            )
    if _empty(conn, "flavor_boosters"):
        food_ids = {r[1].lower(): r[0] for r in conn.execute("SELECT id, name FROM foods")}
        conn.executemany(
            "INSERT INTO flavor_boosters (food_id, grams, tags, note) VALUES (?, ?, ?, ?)",
            [(food_ids[f.lower()], g, t, n) for f, g, t, n in BOOSTERS],
        )
