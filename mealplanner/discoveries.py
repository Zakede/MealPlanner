"""'Try something new': healthy foods people rarely think of, each with one easy recipe.

FOODS and RECIPES use the library's tuple shapes and are added to it; DISCOVERIES drives the suggestion card.
"""
from datetime import timedelta

# name, kcal, protein, carbs, fat (per 100 g), JPY per 100 g, grams per piece, allergens, category
FOODS = [
    ("Canned kidney beans", 110, 7.5, 18.0, 0.5, 80, None, "", "legume"),
    ("Red lentils (dry)", 340, 25.0, 57.0, 1.5, 90, None, "", "legume"),
    ("Canned black beans", 110, 7.0, 17.0, 0.5, 110, None, "", "legume"),
    ("Canned mackerel", 174, 20.9, 0.2, 10.7, 120, None, "fish", "fish"),
    ("Cod fillet", 77, 17.6, 0.1, 0.2, 200, 100, "fish", "fish"),
    ("Barley (dry)", 340, 9.0, 72.0, 1.3, 80, None, "", "grain"),
    ("Buckwheat soba (dry)", 344, 14.0, 66.7, 2.3, 70, None, "buckwheat, wheat", "grain"),
    ("Okra", 30, 2.1, 6.6, 0.2, 150, 10, "", "veg"),
    ("Kabocha", 91, 1.9, 20.6, 0.3, 50, None, "", "veg"),
    ("Cooked brown rice", 152, 2.8, 35.6, 1.0, 40, None, "", "grain"),
    ("Quinoa (dry)", 368, 14.0, 64.0, 6.0, 200, None, "", "grain"),
    ("Enoki mushrooms", 22, 2.7, 7.6, 0.2, 60, None, "", "veg"),
    ("Wakame (rehydrated)", 17, 1.9, 5.9, 0.2, 100, None, "", "veg"),
]

# name, active, total, servings, tags, spice, thaw, types, cuisine, batch, portable, ingredients, steps
RECIPES = [
    ("Kidney bean chili bowl (batch)", 15, 30, 3, "spicy,comfort,savory", 2, 0, "lunch,dinner", "mexican", 1, 1,
     [("Ground chicken", 300), ("Canned kidney beans", 400), ("Canned tomatoes", 400), ("Onion", 150),
      ("Taco spice mix", 15), ("Garlic", 10), ("Cooked rice", 450)],
     "Brown the chicken with chopped onion and garlic, 6 minutes.\nStir in the taco spice for 30 seconds.\n"
     "Add tomatoes and drained beans, simmer 15 minutes until thick.\nServe over rice. Freezes well."),
    ("Red lentil dal (batch)", 10, 30, 3, "comfort,spicy,vegan", 1, 0, "lunch,dinner", "indian", 1, 1,
     [("Red lentils (dry)", 200), ("Canned tomatoes", 200), ("Onion", 120), ("Garlic", 10), ("Ginger", 8),
      ("Curry powder", 10), ("Frozen spinach", 100), ("Cooked rice", 450)],
     "Soften onion, garlic and ginger in a pot, 5 minutes.\nStir in curry powder, then rinsed lentils, tomatoes and "
     "600 ml water.\nSimmer 20 minutes, stirring now and then, until soft.\nStir in spinach. Serve with rice."),
    ("Black bean burrito bowl", 12, 15, 1, "fresh,spicy", 1, 0, "lunch,dinner", "mexican", 0, 1,
     [("Canned black beans", 150), ("Chicken breast", 120), ("Cooked rice", 150), ("Tomato", 80), ("Avocado", 50),
      ("Lemon juice", 10), ("Taco spice mix", 5)],
     "Season the chicken with taco spice, pan-fry 4 minutes a side until cooked through.\n"
     "Warm the drained beans.\nSlice chicken over rice with beans, diced tomato and avocado, squeeze of lemon."),
    ("Saba mackerel rice bowl", 5, 5, 1, "savory,quick", 0, 0, "lunch,dinner", "japanese", 0, 1,
     [("Canned mackerel", 120), ("Cooked rice", 150), ("Cucumber", 60), ("Green onion", 10), ("Ginger", 5),
      ("Soy sauce", 6)],
     "Flake the mackerel over warm rice.\nTop with sliced cucumber, green onion and grated ginger.\nA few drops of soy sauce."),
    ("Miso-glazed cod", 10, 15, 1, "sweet-savory", 0, 0, "dinner", "japanese", 0, 0,
     [("Cod fillet", 150), ("Miso", 15), ("Mirin", 10), ("Frozen broccoli", 100), ("Cooked rice", 150)],
     "Mix miso and mirin, spread over the cod.\nGrill or air fry at 200 °C for 8-10 minutes until it flakes.\n"
     "Microwave the broccoli. Serve with rice."),
    ("Chicken barley soup (batch)", 15, 40, 3, "comfort,savory", 0, 0, "lunch,dinner", "", 1, 1,
     [("Chicken breast", 300), ("Barley (dry)", 90), ("Carrot", 100), ("Onion", 120), ("Cabbage", 150),
      ("Garlic", 6), ("Soy sauce", 10)],
     "Bring 1.2 L water to a boil with the rinsed barley, 15 minutes.\nAdd diced chicken, carrot, onion, garlic.\n"
     "Simmer 15 minutes, add chopped cabbage for the last 5. Season with soy sauce and pepper."),
    ("Cold soba with chicken & egg", 10, 15, 1, "fresh,savory", 0, 0, "lunch", "japanese", 0, 1,
     [("Buckwheat soba (dry)", 90), ("Salad chicken", 100), ("Egg", 50), ("Cucumber", 60), ("Green onion", 10),
      ("Soy sauce", 15), ("Mirin", 10)],
     "Boil the soba as the pack says, rinse in cold water.\nBoil the egg 7 minutes.\n"
     "Top soba with sliced chicken, cucumber, halved egg and green onion.\nDipping sauce: soy, mirin and 60 ml cold water."),
    ("Okra natto rice", 5, 5, 1, "savory", 0, 0, "breakfast,lunch", "japanese", 0, 0,
     [("Natto", 45), ("Okra", 60), ("Cooked rice", 150), ("Egg", 50), ("Soy sauce", 5)],
     "Microwave the okra 1 minute, slice into stars.\nMix natto with its sauce, okra and the raw egg yolk if you like.\n"
     "Pile on warm rice, a drop of soy sauce."),
    ("Kabocha & chicken simmer (batch)", 10, 25, 2, "sweet-savory,comfort", 0, 0, "dinner", "japanese", 1, 1,
     [("Kabocha", 300), ("Chicken thigh", 250), ("Soy sauce", 20), ("Mirin", 20), ("Ginger", 5)],
     "Cut kabocha into chunks, chicken into bites.\nBrown the chicken 3 minutes, add kabocha, soy, mirin, ginger and 200 ml water.\n"
     "Lid on, simmer 15 minutes until the kabocha is soft."),
    ("Brown rice salmon bowl", 12, 15, 1, "fresh,savory", 0, 0, "lunch,dinner", "japanese", 0, 1,
     [("Cooked brown rice", 150), ("Salmon fillet", 100), ("Avocado", 40), ("Cucumber", 50), ("Soy sauce", 8)],
     "Pan-fry or air fry the salmon 8 minutes until it flakes.\nFlake over brown rice with avocado and cucumber.\nDrizzle with soy sauce."),
    ("Quinoa chickpea salad", 10, 20, 1, "fresh,crunchy", 0, 0, "lunch", "", 0, 1,
     [("Quinoa (dry)", 60), ("Canned chickpeas", 100), ("Salad chicken", 100), ("Cucumber", 80), ("Tomato", 80),
      ("Lemon juice", 15), ("Olive oil", 5)],
     "Simmer the rinsed quinoa in 150 ml water, 12 minutes, let it cool.\n"
     "Mix with chickpeas, diced cucumber, tomato and sliced chicken.\nDress with lemon, olive oil, salt and pepper."),
    ("Enoki egg drop soup", 5, 8, 1, "comfort,light", 0, 0, "breakfast,lunch", "chinese", 0, 0,
     [("Enoki mushrooms", 100), ("Egg", 100), ("Green onion", 10), ("Soy sauce", 8), ("Ginger", 3)],
     "Boil 400 ml water with soy sauce and ginger.\nAdd enoki, 2 minutes.\nDrizzle in beaten egg while stirring. Top with green onion."),
    ("Tofu wakame miso soup", 5, 8, 1, "comfort,light", 0, 0, "breakfast", "japanese", 0, 0,
     [("Firm tofu", 100), ("Wakame (rehydrated)", 30), ("Miso", 18), ("Green onion", 5)],
     "Heat 300 ml water, add cubed tofu and wakame.\nTake off the heat, stir in the miso.\nTop with green onion."),
]

# food, why it's worth it, the recipe that uses it
DISCOVERIES = [
    ("Canned kidney beans", "Fibre and plant protein for about ¥80 a can. Makes mince go twice as far.", "Kidney bean chili bowl (batch)"),
    ("Red lentils (dry)", "Cooks in 20 minutes with no soaking. Cheap protein and lots of fibre.", "Red lentil dal (batch)"),
    ("Canned black beans", "Fibre that keeps you full, great in bowls.", "Black bean burrito bowl"),
    ("Canned mackerel", "Omega-3 fats and 20 g protein per 100 g, zero cooking.", "Saba mackerel rice bowl"),
    ("Cod fillet", "Very lean: 18 g protein for 77 kcal.", "Miso-glazed cod"),
    ("Barley (dry)", "Chewy, with far more fibre than rice. Good in soup or mixed 1:3 into rice.", "Chicken barley soup (batch)"),
    ("Buckwheat soba (dry)", "More protein than udon and a nutty taste.", "Cold soba with chicken & egg"),
    ("Okra", "Fibre for almost no calories.", "Okra natto rice"),
    ("Kabocha", "Sweet and filling, full of vitamin A.", "Kabocha & chicken simmer (batch)"),
    ("Cooked brown rice", "The same rice with more fibre, keeps you full longer.", "Brown rice salmon bowl"),
    ("Quinoa (dry)", "A grain with complete protein.", "Quinoa chickpea salad"),
    ("Enoki mushrooms", "22 kcal per 100 g: easy bulk for soups.", "Enoki egg drop soup"),
    ("Wakame (rehydrated)", "Minerals for basically no calories.", "Tofu wakame miso soup"),
]


def candidates(recipes, recent_food_names, on):
    """Discoveries the user can eat and hasn't had lately, in a daily-rotating order."""
    by_name = {r["name"]: r for r in recipes}
    out = []
    for food, why, recipe_name in DISCOVERIES:
        r = by_name.get(recipe_name)
        if not r or not r.get("fits", True) or r.get("pref") in ("never", "try", "favorite"):
            continue
        if food.lower() in recent_food_names:
            continue
        out.append({"food": food, "why": why, "recipe": r})
    if out:
        k = on.toordinal() % len(out)
        out = out[k:] + out[:k]
    return out


def recent_foods(query, on, days=28):
    rows = query("""SELECT DISTINCT lower(f.name) n FROM plan_meals m
                    JOIN recipe_ingredients ri ON ri.recipe_id = m.recipe_id JOIN foods f ON f.id = ri.food_id
                    WHERE m.date >= ? AND m.status IN ('cooked', 'eaten')""", ((on - timedelta(days=days)).isoformat(),))
    return {r["n"] for r in rows}
