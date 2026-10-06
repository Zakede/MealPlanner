"""Built-in food and recipe library. Values are approximate Japanese food-table and supermarket
figures; users edit them to match their labels and receipts."""

LIBRARY_VERSION = 7

# Category drives diet filters: poultry, meat, fish, seafood, egg, dairy, soy, legume, grain,
# veg, fruit, sauce, fat, snack.
# name, kcal, protein, carbs, fat (per 100 g), JPY per 100 g, grams per piece, allergens, category
FOODS = [
    ("Chicken breast", 105, 23.3, 0, 1.9, 85, None, "", "poultry"),
    ("Chicken thigh", 127, 19.0, 0, 5.0, 110, None, "", "poultry"),
    ("Ground chicken", 120, 22.0, 0, 3.5, 110, None, "", "poultry"),
    ("Salad chicken", 105, 24.0, 0.5, 1.0, 230, 110, "", "poultry"),
    ("Pork komagire", 200, 18.5, 0.2, 14.0, 140, None, "", "meat"),
    ("Lean beef", 140, 21.0, 0.4, 5.5, 300, None, "", "meat"),
    ("Ground beef", 251, 17.1, 0.3, 21.1, 250, None, "", "meat"),
    ("Ground pork", 209, 17.7, 0.1, 15.1, 140, None, "", "meat"),
    ("Mixed mince (beef & pork)", 236, 17.3, 0.3, 18.4, 160, None, "", "meat"),
    ("Egg", 142, 12.2, 0.4, 10.2, 40, 60, "egg", "egg"),
    ("Firm tofu", 73, 7.0, 1.5, 4.9, 30, 300, "soy", "soy"),
    ("Atsuage", 143, 10.7, 0.9, 11.3, 50, 150, "soy", "soy"),
    ("Natto", 190, 16.5, 12.1, 10.0, 70, 45, "soy", "soy"),
    ("Frozen edamame", 118, 11.5, 8.9, 6.1, 100, None, "soy", "soy"),
    ("Soy meat (dry)", 345, 50.0, 25.0, 2.0, 150, None, "soy", "soy"),
    ("Canned chickpeas", 171, 9.5, 27.4, 2.5, 90, None, "", "legume"),
    ("Greek yogurt", 60, 10.0, 4.0, 0.4, 140, None, "milk", "dairy"),
    ("Cottage cheese", 105, 13.3, 1.9, 4.5, 200, None, "milk", "dairy"),
    ("Low-fat milk", 46, 3.8, 5.5, 1.0, 25, None, "milk", "dairy"),
    ("Soy milk", 44, 3.6, 3.1, 2.0, 30, None, "soy", "soy"),
    ("Protein powder", 390, 75.0, 8.0, 6.0, 300, None, "milk", "dairy"),
    ("Sliced cheese", 313, 22.7, 1.3, 26.0, 200, 18, "milk", "dairy"),
    ("Pizza cheese", 340, 27.0, 1.0, 26.0, 200, None, "milk", "dairy"),
    ("Canned tuna", 70, 16.0, 0.2, 0.7, 150, 70, "fish", "fish"),
    ("Salmon fillet", 124, 22.3, 0.1, 4.1, 250, 100, "fish", "fish"),
    ("Frozen shrimp", 82, 18.4, 0.3, 0.6, 250, None, "shrimp", "seafood"),
    ("Cooked rice", 156, 2.5, 37.1, 0.3, 30, None, "", "grain"),
    ("Oats", 380, 13.7, 69.0, 5.7, 70, None, "", "grain"),
    ("Bread (shokupan)", 248, 8.9, 46.4, 4.1, 50, 60, "wheat", "grain"),
    ("Pasta (dry)", 347, 12.9, 73.1, 1.8, 40, None, "wheat", "grain"),
    ("Frozen udon", 95, 2.6, 21.6, 0.4, 40, 200, "wheat", "grain"),
    ("Panko", 373, 14.6, 63.4, 6.8, 80, None, "wheat", "grain"),
    ("Potato", 59, 1.8, 17.3, 0.1, 40, 150, "", "veg"),
    ("Sweet potato", 126, 1.2, 31.9, 0.2, 50, 250, "", "veg"),
    ("Shirataki noodles", 7, 0.2, 3.0, 0.0, 60, 200, "", "veg"),
    ("Onion", 37, 1.0, 8.8, 0.1, 40, 200, "", "veg"),
    ("Green onion", 28, 1.8, 6.5, 0.3, 150, 15, "", "veg"),
    ("Green pepper", 22, 0.9, 5.1, 0.2, 100, 35, "", "veg"),
    ("Lettuce", 12, 0.6, 2.8, 0.1, 80, None, "", "veg"),
    ("Cabbage", 23, 1.3, 5.2, 0.2, 25, None, "", "veg"),
    ("Bean sprouts", 15, 1.7, 2.6, 0.1, 15, 200, "", "veg"),
    ("Carrot", 39, 0.7, 9.3, 0.2, 40, 150, "", "veg"),
    ("Tomato", 20, 0.7, 4.7, 0.1, 70, 150, "", "veg"),
    ("Cucumber", 14, 1.0, 3.0, 0.1, 60, 100, "", "veg"),
    ("Eggplant", 22, 1.1, 5.1, 0.1, 80, 80, "", "veg"),
    ("Shimeji mushrooms", 22, 2.7, 4.8, 0.5, 100, 100, "", "veg"),
    ("Avocado", 176, 2.1, 7.9, 17.5, 100, 140, "", "veg"),
    ("Frozen broccoli", 37, 4.3, 5.2, 0.5, 70, None, "", "veg"),
    ("Frozen spinach", 25, 2.9, 3.6, 0.4, 70, None, "", "veg"),
    ("Frozen mixed vegetables", 67, 3.0, 13.5, 0.7, 60, None, "", "veg"),
    ("Canned tomatoes", 20, 0.9, 4.4, 0.1, 50, 400, "", "veg"),
    ("Kimchi", 38, 2.3, 5.4, 0.2, 100, None, "", "veg"),
    ("Garlic", 129, 6.4, 27.5, 0.9, 300, 6, "", "veg"),
    ("Ginger", 30, 0.9, 6.6, 0.3, 200, None, "", "veg"),
    ("Banana", 86, 1.1, 22.5, 0.2, 40, 100, "", "fruit"),
    ("Frozen berries", 50, 0.7, 12.0, 0.3, 120, None, "", "fruit"),
    ("Lemon juice", 24, 0.4, 8.6, 0.2, 100, None, "", "fruit"),
    ("Soy sauce", 76, 7.7, 7.9, 0.0, 50, None, "soy, wheat", "sauce"),
    ("Mirin", 241, 0.3, 43.2, 0.0, 60, None, "", "sauce"),
    ("Miso", 192, 12.5, 21.9, 6.0, 80, None, "soy", "sauce"),
    ("Ponzu", 49, 3.7, 7.8, 0.0, 60, None, "soy, wheat", "sauce"),
    ("Oyster sauce", 105, 7.7, 18.3, 0.3, 120, None, "soy, wheat, shellfish", "sauce"),
    ("Gochujang", 251, 4.9, 54.0, 1.5, 150, None, "soy, wheat", "sauce"),
    ("Chili bean paste", 60, 2.0, 8.0, 2.0, 200, None, "soy", "sauce"),
    ("Half-calorie mayo", 290, 1.4, 3.4, 30.0, 120, None, "egg", "sauce"),
    ("Honey", 329, 0.3, 81.9, 0.0, 150, None, "", "sauce"),
    ("Curry powder", 338, 13.0, 63.3, 12.2, 800, None, "", "sauce"),
    ("Taco spice mix", 330, 14.0, 56.0, 9.0, 600, None, "", "sauce"),
    ("Sesame oil", 890, 0.0, 0.0, 100.0, 150, None, "sesame", "fat"),
    ("Olive oil", 894, 0.0, 0.0, 100.0, 120, None, "", "fat"),
    ("Peanut butter", 600, 25.0, 20.0, 50.0, 120, None, "peanut", "fat"),
    ("Vegetable oil", 921, 0.0, 0.0, 100.0, 60, None, "", "fat"),
    ("Cooking spray", 800, 0.0, 0.0, 90.0, 300, None, "", "fat"),
    ("Garlic powder", 331, 16.6, 72.7, 0.7, 800, None, "", "sauce"),
    ("Grated garlic (tube)", 171, 4.1, 33.9, 3.0, 450, None, "", "sauce"),
    ("Ginger paste (tube)", 48, 0.7, 9.6, 0.6, 400, None, "", "sauce"),
    ("Ground ginger", 335, 9.0, 71.6, 4.2, 900, None, "", "sauce"),
    ("Dried green onion", 300, 20.0, 55.0, 3.0, 1500, None, "", "veg"),
    ("Onion powder", 341, 10.4, 79.1, 1.0, 700, None, "", "sauce"),
    ("Monk fruit sweetener", 0, 0.0, 0.0, 0.0, 250, None, "", "sauce"),
    ("Low-sodium soy sauce", 69, 7.7, 7.9, 0.0, 70, None, "soy, wheat", "sauce"),
    ("Microwave rice pack", 152, 2.3, 34.6, 0.3, 65, 200, "", "grain"),
    ("Chili crisp", 600, 3.0, 10.0, 60.0, 300, None, "sesame, soy", "sauce"),
    ("Rice crackers", 380, 7.0, 85.0, 1.0, 150, None, "soy", "snack"),
    ("Light popcorn", 400, 11.0, 70.0, 9.0, 200, None, "", "snack"),
]

# Recipes are written for beginners: short steps, clear doneness cues, one pan where possible.
# name, active_min, total_min, servings, tags, spice, thaw_hours, meal_types, cuisine, batch_ok, portable,
# ingredients [(food, grams for the whole recipe)], steps
RECIPES = [
    # breakfast
    ("Protein overnight oats", 3, 3, 1, "sweet,creamy", 0, 0, "breakfast", "", 0, 1,
     [("Oats", 50), ("Low-fat milk", 200), ("Protein powder", 30), ("Frozen berries", 50)],
     "Stir oats, milk and protein powder in a jar.\nTop with berries, lid on, fridge overnight."),
    ("Greek yogurt berry bowl", 3, 3, 1, "sweet,creamy,crunchy", 0, 0, "breakfast,snack", "", 0, 1,
     [("Greek yogurt", 200), ("Frozen berries", 80), ("Oats", 30), ("Honey", 8)],
     "Thaw the berries for a minute in the microwave so they bleed into the yogurt.\n"
     "Spoon yogurt into a bowl, add berries, oats and a drizzle of honey."),
    ("Egg & cheese toast", 8, 8, 1, "cheesy,savory", 0, 0, "breakfast", "western", 0, 0,
     [("Bread (shokupan)", 60), ("Egg", 120), ("Sliced cheese", 18), ("Tomato", 60)],
     "Scramble the eggs on low heat, stirring, until just set.\n"
     "Toast the bread with the cheese on top until it melts.\nPile on eggs and sliced tomato. Pepper on top."),
    ("Natto egg rice", 3, 3, 1, "savory,quick", 0, 0, "breakfast,lunch", "japanese", 0, 0,
     [("Cooked rice", 150), ("Natto", 45), ("Egg", 60), ("Green onion", 10), ("Soy sauce", 5)],
     "Warm the rice.\nStir the natto hard with its sauce until stringy.\n"
     "Top the rice with natto, a soft-boiled egg and sliced green onion."),
    ("Cottage cheese veggie scramble", 8, 8, 1, "savory,creamy,low-carb", 0, 0, "breakfast", "western", 0, 0,
     [("Egg", 180), ("Cottage cheese", 60), ("Frozen spinach", 50), ("Tomato", 60), ("Olive oil", 3)],
     "Warm the spinach in a pan with the oil.\nAdd beaten eggs, stir slowly on low heat.\n"
     "Fold in cottage cheese just before the eggs set. Serve with chopped tomato."),
    ("Tofu scramble", 10, 10, 1, "savory,vegan", 0, 0, "breakfast,lunch", "western", 0, 0,
     [("Firm tofu", 200), ("Frozen spinach", 50), ("Onion", 40), ("Soy sauce", 5), ("Curry powder", 2),
      ("Olive oil", 5)],
     "Soften the chopped onion in the oil, 3 minutes.\nCrumble in the tofu with your hands.\n"
     "Add curry powder (for colour), soy sauce and spinach. Fry 4 minutes until hot and a bit golden."),
    ("Peanut butter banana toast", 3, 3, 1, "sweet,nutty", 0, 0, "breakfast", "western", 0, 0,
     [("Bread (shokupan)", 60), ("Peanut butter", 15), ("Banana", 100), ("Greek yogurt", 100)],
     "Toast the bread, spread peanut butter, top with sliced banana.\nHave the yogurt on the side."),

    # lunch / dinner
    ("Chicken teriyaki rice bowl", 15, 20, 1, "sweet-savory", 0, 0, "lunch,dinner", "japanese", 0, 1,
     [("Chicken breast", 150), ("Cooked rice", 180), ("Soy sauce", 15), ("Mirin", 15), ("Frozen broccoli", 80)],
     "Cut the chicken into bite-size pieces.\n"
     "Fry on medium-high until browned and no pink inside, about 6 minutes.\n"
     "Add soy sauce and mirin, bubble until glossy.\nMicrowave the broccoli 2 minutes. Serve over rice."),
    ("Ginger pork with cabbage", 12, 15, 1, "savory,sweet-savory", 0, 0, "lunch,dinner", "japanese", 0, 1,
     [("Pork komagire", 120), ("Cabbage", 120), ("Ginger", 10), ("Soy sauce", 15), ("Mirin", 15),
      ("Cooked rice", 150)],
     "Grate the ginger and mix with soy sauce and mirin.\nShred the cabbage thinly.\n"
     "Fry the pork on high heat until no pink is left, about 3 minutes.\n"
     "Pour in the sauce and toss for 1 minute. Serve with cabbage and rice."),
    ("Oyakodon", 15, 20, 1, "sweet-savory,comfort", 0, 0, "lunch,dinner", "japanese", 0, 0,
     [("Chicken thigh", 120), ("Egg", 120), ("Onion", 60), ("Cooked rice", 180), ("Soy sauce", 15), ("Mirin", 15)],
     "Simmer sliced onion in soy sauce, mirin and 60 ml water for 3 minutes.\n"
     "Add bite-size chicken and simmer until cooked through, about 6 minutes.\n"
     "Pour in beaten eggs, cover for 1 minute, slide over rice."),
    ("Chicken & egg udon", 10, 12, 1, "savory,comfort", 0, 0, "lunch,dinner", "japanese", 0, 0,
     [("Frozen udon", 200), ("Chicken breast", 100), ("Egg", 60), ("Soy sauce", 15), ("Mirin", 10),
      ("Frozen spinach", 50), ("Green onion", 10)],
     "Bring 350 ml water with soy sauce and mirin to a simmer.\nAdd thin-sliced chicken, cook 5 minutes.\n"
     "Add udon and spinach, crack in the egg, cook 2 minutes. Top with green onion."),
    ("Pork & tofu kimchi stir-fry", 15, 15, 1, "spicy,garlicky,sour", 2, 0, "lunch,dinner", "korean", 0, 0,
     [("Pork komagire", 100), ("Firm tofu", 150), ("Kimchi", 80), ("Onion", 50), ("Bean sprouts", 100),
      ("Sesame oil", 5), ("Gochujang", 10)],
     "Cube the tofu and slice the onion.\nFry the pork in sesame oil on high heat until no pink is left.\n"
     "Add onion and kimchi, fry 2 minutes.\nAdd bean sprouts, tofu and gochujang, toss gently 2 minutes."),
    ("Beef & broccoli rice", 12, 15, 1, "savory,garlicky", 0, 0, "lunch,dinner", "chinese", 1, 1,
     [("Lean beef", 120), ("Frozen broccoli", 120), ("Cooked rice", 150), ("Oyster sauce", 15),
      ("Soy sauce", 10), ("Garlic", 6), ("Ginger", 5)],
     "Slice the beef thin against the grain.\nMicrowave the broccoli 2 minutes.\n"
     "Fry garlic and ginger 30 seconds, add beef, sear 2 minutes on high.\n"
     "Add broccoli, oyster sauce and soy sauce, toss 1 minute. Serve over rice."),
    ("Beef & egg gyudon", 12, 15, 1, "sweet-savory,comfort", 0, 0, "lunch,dinner", "japanese", 0, 0,
     [("Lean beef", 120), ("Onion", 80), ("Egg", 60), ("Soy sauce", 15), ("Mirin", 15), ("Cooked rice", 150)],
     "Simmer sliced onion in soy sauce, mirin and 80 ml water until soft, 4 minutes.\n"
     "Add thin beef, simmer 2 minutes until browned.\nServe over rice with a soft-boiled egg."),
    ("Garlic soy chicken thighs & potatoes", 15, 30, 1, "garlicky,sweet-savory,crispy", 0, 0, "dinner", "western", 0, 0,
     [("Chicken thigh", 180), ("Potato", 200), ("Garlic", 8), ("Soy sauce", 15), ("Honey", 8), ("Olive oil", 5)],
     "Cut potatoes into wedges, microwave 4 minutes.\n"
     "Pan-fry chicken skin-side down in the oil, 6 minutes, then flip and add potatoes.\n"
     "Cook 8 minutes more until the chicken juices run clear.\n"
     "Add crushed garlic, soy sauce and honey, toss until sticky."),
    ("Crispy panko chicken with cabbage", 15, 25, 1, "crunchy,savory", 0, 0, "dinner", "japanese", 0, 0,
     [("Chicken breast", 180), ("Panko", 20), ("Egg", 30), ("Cabbage", 100), ("Half-calorie mayo", 10),
      ("Lemon juice", 10), ("Olive oil", 5)],
     "Butterfly the chicken so it's even. Dip in beaten egg, press into panko.\n"
     "Pan-fry in the oil on medium, 5 minutes per side, until golden and cooked through.\n"
     "Serve with shredded cabbage, lemon and mayo."),
    ("Chicken burrito bowl", 15, 15, 1, "spicy,fresh,savory", 1, 0, "lunch,dinner", "mexican", 1, 1,
     [("Chicken breast", 150), ("Cooked rice", 150), ("Canned chickpeas", 60), ("Tomato", 80),
      ("Avocado", 50), ("Lettuce", 40), ("Lemon juice", 10), ("Taco spice mix", 6)],
     "Toss bite-size chicken with the spice mix, fry until cooked through, 6 minutes.\n"
     "Warm the chickpeas in the same pan.\nBuild the bowl: rice, lettuce, chicken, chickpeas, tomato, avocado.\n"
     "Squeeze lemon over everything."),
    ("Chicken tomato pasta", 15, 20, 1, "garlicky,cheesy,comfort", 0, 0, "lunch,dinner", "italian", 1, 1,
     [("Chicken breast", 150), ("Pasta (dry)", 80), ("Canned tomatoes", 200), ("Garlic", 6), ("Olive oil", 5),
      ("Pizza cheese", 15)],
     "Boil the pasta 1 minute less than the packet says.\n"
     "Fry bite-size chicken in the oil until cooked through, add garlic for 30 seconds.\n"
     "Add tomatoes, simmer 5 minutes, toss in the pasta with a splash of pasta water. Top with cheese."),
    ("Mapo tofu", 15, 15, 1, "spicy,garlicky,comfort", 3, 0, "dinner", "chinese", 0, 0,
     [("Firm tofu", 250), ("Ground chicken", 80), ("Chili bean paste", 15), ("Garlic", 6), ("Ginger", 5),
      ("Soy sauce", 10), ("Green onion", 10), ("Cooked rice", 150)],
     "Cube the tofu.\nFry ground chicken until crumbly, add garlic, ginger and chili bean paste for 1 minute.\n"
     "Add 120 ml water and soy sauce, slide in the tofu, simmer 3 minutes.\nTop with green onion, serve with rice."),
    ("Miso eggplant & chicken", 15, 15, 1, "sweet-savory,comfort", 0, 0, "dinner", "japanese", 0, 1,
     [("Eggplant", 160), ("Ground chicken", 120), ("Miso", 12), ("Mirin", 10), ("Garlic", 4), ("Cooked rice", 150),
      ("Olive oil", 5)],
     "Cut the eggplant into chunks, fry in the oil until soft and browned, 6 minutes.\n"
     "Push aside, cook the chicken until crumbly with the garlic.\n"
     "Mix miso and mirin with 2 tablespoons water, toss through. Serve with rice."),
    ("Chicken, mushroom & tofu miso soup set", 12, 15, 1, "savory,comfort", 0, 0, "dinner", "japanese", 0, 0,
     [("Chicken breast", 120), ("Shimeji mushrooms", 100), ("Firm tofu", 100), ("Miso", 18), ("Green onion", 10),
      ("Cooked rice", 150)],
     "Simmer thin chicken and mushrooms in 400 ml water for 6 minutes.\nAdd cubed tofu for 2 minutes.\n"
     "Turn off the heat, dissolve the miso. Top with green onion, serve with rice."),
    ("Keto chicken thighs with avocado salad", 15, 20, 1, "fresh,savory,low-carb", 0, 0, "lunch,dinner", "western", 0, 0,
     [("Chicken thigh", 200), ("Avocado", 70), ("Tomato", 80), ("Cucumber", 80), ("Lemon juice", 10),
      ("Olive oil", 5)],
     "Season and pan-fry the chicken 6 minutes per side until the juices run clear.\n"
     "Chop avocado, tomato and cucumber, dress with lemon, oil and salt.\nSlice the chicken over the salad."),
    ("Beef & mushroom stir-fry", 12, 12, 1, "savory,garlicky,low-carb", 0, 0, "dinner", "chinese", 0, 0,
     [("Lean beef", 150), ("Shimeji mushrooms", 100), ("Green pepper", 70), ("Bean sprouts", 100),
      ("Soy sauce", 12), ("Garlic", 6), ("Sesame oil", 5)],
     "Slice beef and peppers thin.\nSear the beef in sesame oil on high heat, 2 minutes, set aside.\n"
     "Fry mushrooms, pepper and sprouts 3 minutes, add garlic, beef and soy sauce, toss 1 minute."),
    ("Chicken & vegetable curry (batch)", 25, 50, 4, "spicy,garlicky,comfort", 2, 0, "lunch,dinner", "japanese", 1, 1,
     [("Chicken breast", 600), ("Onion", 200), ("Carrot", 150), ("Frozen broccoli", 200),
      ("Canned tomatoes", 400), ("Curry powder", 15), ("Garlic", 12), ("Cooked rice", 720)],
     "Dice the onion, carrot and chicken. Crush the garlic.\n"
     "Soften the onion and garlic in a non-stick pot, 5 minutes.\nAdd chicken and curry powder, cook 3 minutes.\n"
     "Add tomatoes, carrot and 200 ml water, simmer 25 minutes.\n"
     "Add broccoli for the last 5 minutes. Cool quickly and refrigerate portions within an hour."),
    ("Chickpea & spinach curry (batch)", 15, 35, 3, "spicy,comfort,vegan", 2, 0, "lunch,dinner", "indian", 1, 1,
     [("Canned chickpeas", 400), ("Canned tomatoes", 400), ("Onion", 150), ("Frozen spinach", 150),
      ("Curry powder", 12), ("Garlic", 10), ("Ginger", 8), ("Cooked rice", 450)],
     "Soften onion, garlic and ginger in a pot, 5 minutes.\nStir in curry powder for 30 seconds.\n"
     "Add tomatoes and chickpeas, simmer 15 minutes.\nStir in spinach until hot. Serve with rice."),
    ("Soy meat bolognese (batch)", 15, 30, 3, "savory,garlicky,comfort,vegan", 0, 0, "lunch,dinner", "italian", 1, 1,
     [("Soy meat (dry)", 120), ("Pasta (dry)", 240), ("Canned tomatoes", 400), ("Onion", 120), ("Carrot", 80),
      ("Garlic", 10), ("Olive oil", 8), ("Soy sauce", 10)],
     "Soak the soy meat in hot water 10 minutes, squeeze dry.\n"
     "Soften chopped onion, carrot and garlic in the oil, 5 minutes.\n"
     "Add soy meat and soy sauce, fry 3 minutes, then tomatoes. Simmer 10 minutes.\nToss with cooked pasta."),
    ("Atsuage & vegetable stir-fry", 12, 12, 1, "savory,crunchy,vegan", 0, 0, "lunch,dinner", "japanese", 0, 0,
     [("Atsuage", 150), ("Cabbage", 100), ("Bean sprouts", 100), ("Soy sauce", 12), ("Mirin", 10), ("Ginger", 5),
      ("Cooked rice", 150)],
     "Cut the atsuage into strips and fry in a dry pan until crisp, 4 minutes.\n"
     "Add cabbage and sprouts, fry 3 minutes on high.\nAdd grated ginger, soy sauce and mirin, toss. Serve with rice."),
    ("Edamame tofu protein box", 5, 5, 1, "savory,vegan", 0, 0, "lunch", "japanese", 0, 1,
     [("Firm tofu", 150), ("Frozen edamame", 80), ("Cooked rice", 150), ("Cucumber", 60), ("Soy sauce", 10),
      ("Sesame oil", 3)],
     "Thaw the edamame under warm water.\nPack rice, cubed tofu, edamame and sliced cucumber.\n"
     "Dress with soy sauce and sesame oil just before eating."),
    ("Chickpea & egg salad box", 8, 8, 1, "fresh,creamy", 0, 0, "lunch", "western", 0, 1,
     [("Canned chickpeas", 120), ("Egg", 60), ("Cucumber", 80), ("Tomato", 80), ("Half-calorie mayo", 10),
      ("Lemon juice", 10)],
     "Mash half the chickpeas with mayo and lemon.\nMix in the rest, chopped boiled egg, cucumber and tomato.\n"
     "Season with salt and pepper. Keeps 2 days."),
    ("Salad chicken rice bowl", 3, 3, 1, "fresh,quick", 0, 0, "lunch", "japanese", 0, 1,
     [("Salad chicken", 110), ("Cooked rice", 180), ("Cucumber", 60), ("Ponzu", 15)],
     "Pack rice, sliced salad chicken and cucumber.\nPonzu in a little cup to pour at lunch."),
    ("Tuna onigiri & boiled eggs", 10, 10, 1, "savory", 0, 0, "lunch", "japanese", 0, 1,
     [("Cooked rice", 200), ("Canned tuna", 70), ("Egg", 120), ("Half-calorie mayo", 8)],
     "Mix drained tuna with mayo.\nShape two onigiri around the tuna with wet, salted hands.\n"
     "Pack with two boiled eggs (boil a batch ahead)."),
    ("Easy salmon teriyaki", 12, 15, 1, "sweet-savory", 0, 0, "dinner", "japanese", 0, 0,
     [("Salmon fillet", 120), ("Soy sauce", 12), ("Mirin", 12), ("Frozen broccoli", 100), ("Cooked rice", 150)],
     "Pat the salmon dry. Pan-fry skin-side down on medium, 4 minutes.\n"
     "Flip, cook 3 minutes more until it flakes with a fork.\n"
     "Add soy sauce and mirin, spoon over as it bubbles. Serve with broccoli and rice."),
    ("Garlic shrimp fried rice", 15, 20, 2, "garlicky", 0, 12, "lunch,dinner", "chinese", 1, 1,
     [("Frozen shrimp", 200), ("Cooked rice", 300), ("Egg", 120), ("Frozen mixed vegetables", 150),
      ("Soy sauce", 15), ("Sesame oil", 5), ("Garlic", 6)],
     "Thaw the shrimp in the fridge overnight.\nScramble the eggs in sesame oil and set aside.\n"
     "Fry garlic and shrimp until pink, about 3 minutes.\nAdd vegetables and rice, fry 4 minutes, then the eggs and soy sauce."),

    # plant-based and low-carb extras
    ("Peanut butter soy milk oats", 3, 3, 1, "sweet,nutty,vegan", 0, 0, "breakfast", "", 0, 1,
     [("Oats", 50), ("Soy milk", 200), ("Peanut butter", 15), ("Banana", 60)],
     "Stir oats, soy milk and peanut butter in a jar.\nTop with sliced banana, fridge overnight or microwave 2 minutes."),
    ("Natto rice bowl", 3, 3, 1, "savory,quick,vegan", 0, 0, "breakfast,lunch", "japanese", 0, 0,
     [("Cooked rice", 150), ("Natto", 90), ("Green onion", 10), ("Soy sauce", 5), ("Kimchi", 40)],
     "Warm the rice.\nStir two packs of natto hard with their sauce.\nTop with natto, kimchi and green onion."),
    ("Smashed chickpea salad box", 8, 8, 1, "fresh,creamy,vegan", 0, 0, "lunch", "western", 0, 1,
     [("Canned chickpeas", 150), ("Cucumber", 80), ("Tomato", 80), ("Avocado", 40), ("Lemon juice", 15),
      ("Bread (shokupan)", 60)],
     "Mash half the chickpeas with avocado and lemon.\nMix in the rest, chopped cucumber and tomato, salt and pepper.\n"
     "Pack with bread to make a sandwich at lunch."),
    ("Teriyaki tofu steak", 12, 15, 1, "sweet-savory,crispy,vegan", 0, 0, "dinner", "japanese", 0, 0,
     [("Firm tofu", 300), ("Soy sauce", 15), ("Mirin", 15), ("Ginger", 5), ("Frozen broccoli", 100),
      ("Cooked rice", 150), ("Olive oil", 5)],
     "Press the tofu between paper towels for 5 minutes, slice into thick steaks.\n"
     "Pan-fry in the oil on medium-high until golden, 4 minutes per side.\n"
     "Add soy sauce, mirin and grated ginger, spoon over until sticky. Serve with broccoli and rice."),
    ("Soy meat mapo tofu", 15, 15, 1, "spicy,garlicky,vegan", 3, 0, "dinner", "chinese", 0, 0,
     [("Firm tofu", 250), ("Soy meat (dry)", 25), ("Chili bean paste", 15), ("Garlic", 6), ("Ginger", 5),
      ("Soy sauce", 10), ("Green onion", 10), ("Cooked rice", 150)],
     "Soak the soy meat in hot water 5 minutes and squeeze dry.\n"
     "Fry it with garlic, ginger and chili bean paste for 2 minutes.\n"
     "Add 120 ml water, soy sauce and cubed tofu, simmer 3 minutes. Top with green onion."),
    ("Edamame chickpea fried rice", 12, 12, 1, "savory,garlicky,vegan", 0, 0, "lunch,dinner", "chinese", 0, 1,
     [("Cooked rice", 150), ("Frozen edamame", 80), ("Canned chickpeas", 80), ("Frozen mixed vegetables", 80),
      ("Garlic", 6), ("Soy sauce", 12), ("Sesame oil", 5)],
     "Fry garlic in sesame oil 30 seconds.\nAdd vegetables, edamame and chickpeas, fry 3 minutes.\n"
     "Add rice and soy sauce, fry on high 3 minutes until a little crispy."),
    ("Keto chicken & egg salad box", 8, 8, 1, "fresh,creamy,low-carb", 0, 0, "lunch", "western", 0, 1,
     [("Salad chicken", 110), ("Egg", 120), ("Avocado", 50), ("Cucumber", 80), ("Lettuce", 40),
      ("Half-calorie mayo", 10)],
     "Slice the salad chicken and boiled eggs.\nPack over lettuce and cucumber with avocado.\n"
     "Mayo in a little cup to add at lunch."),
    ("Keto tofu & pork stir-fry", 12, 12, 1, "savory,garlicky,low-carb", 1, 0, "lunch,dinner", "japanese", 0, 1,
     [("Pork komagire", 100), ("Firm tofu", 150), ("Cabbage", 120), ("Shimeji mushrooms", 80), ("Garlic", 5),
      ("Soy sauce", 10), ("Sesame oil", 5)],
     "Cube the tofu and fry in sesame oil until golden, set aside.\n"
     "Fry the pork until no pink is left, add mushrooms, cabbage and garlic, 3 minutes.\n"
     "Return the tofu, add soy sauce, toss 1 minute."),

    # snacks
    ("Salad chicken", 0, 0, 1, "quick", 0, 0, "snack", "", 0, 1, [("Salad chicken", 110)], "Open and eat."),
    ("Boiled eggs", 2, 12, 1, "quick", 0, 0, "snack,breakfast", "", 1, 1, [("Egg", 120)],
     "Boil for 8 minutes, cool in cold water, peel."),
    ("Greek yogurt cup", 0, 0, 1, "sweet,creamy", 0, 0, "snack", "", 0, 1, [("Greek yogurt", 150)],
     "Eat as is, or add cinnamon."),
    ("Salted edamame", 3, 3, 1, "savory,quick", 0, 0, "snack", "japanese", 0, 1, [("Frozen edamame", 100)],
     "Microwave 2 minutes, sprinkle with salt."),
    ("Cottage cheese & berries", 2, 2, 1, "sweet,creamy", 0, 0, "snack", "", 0, 1,
     [("Cottage cheese", 100), ("Frozen berries", 50)], "Top the cottage cheese with half-thawed berries."),
    ("Rice crackers", 0, 0, 1, "crunchy", 0, 0, "snack", "japanese", 0, 1, [("Rice crackers", 30)],
     "Portion 30 g into a bowl rather than eating from the bag."),
    ("Light popcorn", 0, 0, 1, "crunchy", 0, 0, "snack", "", 0, 1, [("Light popcorn", 25)],
     "Portion 25 g. Season with chili powder or nori if you like."),
    ("Beef & tofu soboro bowl", 12, 15, 1, "savory,sweet-savory", 0, 0, "lunch,dinner", "japanese", 1, 1,
     [("Ground beef", 80), ("Firm tofu", 150), ("Ginger", 5), ("Soy sauce", 15), ("Mirin", 10), ("Green onion", 10),
      ("Cooked rice", 150)],
     "Fry the ground beef in a dry pan, breaking it up, until browned, 4 minutes.\n"
     "Crumble in the tofu with grated ginger and cook 3 minutes until dry and crumbly.\n"
     "Add soy sauce and mirin, stir until absorbed. Spoon over rice, top with green onion."),
    ("Light mapo tofu", 12, 15, 1, "spicy,garlicky,savory", 2, 0, "lunch,dinner", "chinese", 1, 0,
     [("Ground pork", 70), ("Firm tofu", 250), ("Chili bean paste", 10), ("Garlic", 5), ("Ginger", 5),
      ("Soy sauce", 5), ("Green onion", 10), ("Cooked rice", 150)],
     "Cube the tofu. Fry the ground pork until browned and no pink is left, 4 minutes.\n"
     "Add garlic, ginger and chili bean paste, fry 30 seconds.\n"
     "Add 120 ml water and soy sauce, slide in the tofu and simmer 4 minutes. Top with green onion, serve with rice."),
    ("Hamburg steak with cabbage", 20, 30, 1, "savory,comfort", 0, 0, "dinner", "japanese", 1, 0,
     [("Mixed mince (beef & pork)", 120), ("Onion", 50), ("Egg", 30), ("Panko", 10), ("Cabbage", 100),
      ("Soy sauce", 10), ("Mirin", 10), ("Cooked rice", 150)],
     "Chop the onion finely. Mix with the mince, egg, panko and a pinch of salt; shape into a thick patty.\n"
     "Fry 3 minutes per side, then add 50 ml water, cover and steam 6 minutes until cooked through (75 °C inside).\n"
     "Add soy sauce and mirin to the pan and spoon the glaze over. Serve with shredded cabbage and rice."),
    ("Air fryer garlic chicken & rice bowl", 8, 20, 1, "garlicky,savory,crispy", 0, 0, "lunch,dinner", "", 1, 1,
     [("Chicken breast", 150), ("Garlic", 5), ("Soy sauce", 10), ("Olive oil", 3), ("Frozen broccoli", 100),
      ("Cooked rice", 150)],
     "Cut the chicken into thick strips. Mix with crushed garlic, soy sauce and oil.\n"
     "Air fry at 200 °C for 12-14 minutes, shaking halfway, until 75 °C inside and golden at the edges.\n"
     "Add the broccoli to the basket for the last 5 minutes. Serve over rice."),
    ("Air fryer crispy thighs & potatoes", 10, 30, 1, "crispy,garlicky,comfort", 0, 0, "dinner", "western", 0, 0,
     [("Chicken thigh", 150), ("Potato", 200), ("Garlic", 6), ("Olive oil", 5), ("Curry powder", 2)],
     "Cut the potatoes into wedges, mix with half the oil and a pinch of salt.\n"
     "Rub the chicken with garlic, curry powder, salt and the rest of the oil.\n"
     "Air fry the potatoes at 200 °C for 10 minutes, add the chicken skin side up and air fry 15 more minutes until 75 °C inside."),
    ("Air fryer tandoori-style chicken", 10, 25, 1, "spicy,sour,savory", 1, 0, "lunch,dinner", "indian", 1, 1,
     [("Chicken breast", 150), ("Greek yogurt", 50), ("Curry powder", 5), ("Garlic", 5), ("Lemon juice", 10),
      ("Cabbage", 80), ("Cooked rice", 150)],
     "Mix yogurt, curry powder, grated garlic, lemon juice and salt. Coat the chicken pieces (overnight is best, 10 minutes works).\n"
     "Air fry at 200 °C for 14 minutes, turning once, until charred at the edges and 75 °C inside.\n"
     "Serve with shredded cabbage and rice."),
    ("Air fryer panko chicken", 12, 25, 1, "crispy,crunchy,savory", 0, 0, "lunch,dinner", "", 1, 1,
     [("Chicken breast", 150), ("Egg", 30), ("Panko", 15), ("Cabbage", 100), ("Half-calorie mayo", 10),
      ("Cooked rice", 150)],
     "Slice the chicken into cutlets, season with salt. Dip in beaten egg, then press into panko.\n"
     "Air fry at 200 °C for 12 minutes, flipping halfway, until crunchy and 75 °C inside.\n"
     "Serve with shredded cabbage, a little half-calorie mayo and rice."),
    ("Air fryer gochujang chicken bowl", 10, 22, 1, "spicy,sweet-savory,crispy", 2, 0, "lunch,dinner", "korean", 1, 1,
     [("Chicken thigh", 130), ("Gochujang", 15), ("Soy sauce", 5), ("Honey", 5), ("Bean sprouts", 100),
      ("Cooked rice", 150)],
     "Cut the chicken into bite-size pieces. Mix gochujang, soy sauce and honey; coat the chicken.\n"
     "Air fry at 190 °C for 14 minutes, shaking halfway, until sticky and 75 °C inside.\n"
     "Microwave the bean sprouts 2 minutes. Serve everything over rice."),
]

# Built-in recipes from earlier versions that are no longer shipped.
REMOVED_RECIPES = [
    "Buldak noodles with onion, green pepper & lettuce",
    "Buldak chicken & cabbage bowl",
    "Natto egg rice with kimchi",
    "Saba rice bowl with cabbage",
    "Greek yogurt oat bowl",
    "Salad chicken kimchi rice",
    "Tofu & cabbage protein box",
    "Salmon, tofu & miso soup set",
]

# food, grams, tags, note
BOOSTERS = [
    ("Kimchi", 50, "spicy,sour", "Crunch and heat for about 20 kcal"),
    ("Soy sauce", 10, "savory", "Salty depth for under 10 kcal"),
    ("Sesame oil", 3, "nutty", "A few drops go a long way (27 kcal)"),
    ("Chili crisp", 8, "spicy,crunchy", "Big flavour, about 50 kcal"),
    ("Gochujang", 10, "spicy,sweet-savory", "Sweet heat for 25 kcal"),
    ("Garlic", 6, "garlicky", "One clove, almost no calories"),
    ("Lemon juice", 10, "fresh,sour", "Brightens anything heavy"),
    ("Ponzu", 15, "fresh,sour,savory", "Citrus soy for 7 kcal"),
    ("Green onion", 10, "fresh", "Freshness and crunch"),
]

# chain, item, kcal, protein, yen (approximate, check the label in store)
QUICK_PICKS = [
    ("Konbini", "Salad chicken (plain)", 115, 24.0, 298),
    ("Konbini", "Salad chicken bar", 70, 12.0, 168),
    ("Konbini", "Boiled egg", 80, 6.5, 98),
    ("Konbini", "Greek yogurt cup", 92, 10.3, 170),
    ("Konbini", "Milk protein drink", 102, 15.0, 160),
    ("Konbini", "Tofu bar", 120, 12.0, 150),
    ("Konbini", "Salmon onigiri", 180, 4.5, 180),
    ("Konbini", "Tuna mayo onigiri", 230, 5.0, 160),
    ("Konbini", "Egg sandwich", 330, 12.0, 300),
    ("Konbini", "Curry pan", 330, 6.5, 160),
    ("Konbini", "Melon pan", 420, 7.5, 150),
    ("Konbini", "Famichiki", 252, 13.0, 230),
    ("Konbini", "Karaage-kun (5)", 220, 14.0, 250),
    ("Konbini", "Nikuman", 230, 8.0, 180),
    ("Konbini", "Cup noodle", 350, 9.0, 230),
    ("Konbini", "Protein bar", 190, 15.0, 160),
    ("Konbini", "Cafe latte (M)", 130, 6.5, 200),
    ("Konbini", "Banana", 90, 1.0, 120),
    ("Konbini", "Cold soba with chicken", 320, 15.0, 450),
    ("Konbini", "Edamame cup", 130, 11.0, 200),
    ("Konbini", "Green salad", 30, 1.5, 250),
    ("Konbini", "Chocolate bar", 280, 4.0, 130),
    ("Konbini", "Potato chips (small)", 330, 3.5, 150),
    ("McDonald's", "Hamburger", 256, 12.8, 200),
    ("McDonald's", "Cheeseburger", 307, 15.8, 230),
    ("McDonald's", "Double cheeseburger", 457, 26.5, 430),
    ("McDonald's", "Chicken McNuggets (5)", 270, 15.9, 290),
    ("McDonald's", "Egg McMuffin", 311, 19.2, 250),
    ("McDonald's", "Fries (M)", 409, 5.3, 330),
    ("McDonald's", "Side salad", 10, 0.7, 310),
]

# craving, swap, kcal before, kcal after, note
CRAVING_SWAPS = [
    ("Potato chips", "Light popcorn or rice crackers", 336, 100, "Same crunch, a third of the calories"),
    ("Ice cream", "Frozen Greek yogurt with berries", 250, 140, "Freeze the cup for an hour"),
    ("Chocolate", "Cocoa protein shake", 280, 130, "Protein powder + cocoa + milk"),
    ("Karaage", "Crispy panko chicken", 450, 330, "Pan-fried, not deep-fried"),
    ("Instant ramen", "Chicken & egg udon", 450, 420, "Same comfort, three times the protein"),
    ("Soda", "Zero cola or sparkling water", 140, 0, ""),
    ("Pizza", "Egg & cheese toast", 700, 380, ""),
]

# Taste booster guide: ways to add flavour without many calories.
# Each item: name, Japanese name, kcal per serving, serving, how to use, where to get it, allergens, rough JPY.
TASTE_GUIDE = [
    ("make", "Make it yourself", "手作り", "Low-calorie sauces from things you already have.", [
        ("Yogurt mayo", "ヨーグルトマヨ", 15, "1 tbsp", "Greek yogurt + mustard + lemon + salt. For egg salad, tuna, wraps.", "Make it", "dairy", 0),
        ("Tzatziki", "ザジキ", 12, "1 tbsp", "Yogurt + grated cucumber + garlic + dill. For chicken and rice bowls.", "Make it", "dairy", 0),
        ("Ginger ponzu", "生姜ポン酢", 10, "1 tbsp", "Ponzu + grated ginger + green onion. For tofu, gyoza, pork shabu.", "Make it", "soy, wheat", 0),
        ("Negi shio", "ねぎ塩だれ", 15, "1 tbsp", "Chopped green onion + salt + lemon + 3 drops sesame oil. For grilled chicken.", "Make it", "sesame", 0),
        ("Gochujang yogurt", "コチュジャンヨーグルト", 40, "3 tbsp", "1 tsp gochujang into 3 tbsp yogurt. Sweet heat dip.", "Make it", "soy, wheat, dairy", 0),
        ("Light teriyaki", "低カロリー照り焼き", 12, "1 tbsp", "Soy + monk fruit sweetener + ginger + pinch of starch, simmer until glossy.", "Make it", "soy, wheat", 0),
        ("Miso yuzu dressing", "柚子味噌", 20, "1 tbsp", "Miso + rice vinegar + yuzu or lemon juice. For salads and steamed veg.", "Make it", "soy", 0),
        ("Salsa fresca", "サルサ", 5, "1 tbsp", "Diced tomato + onion + lemon + chili + salt. For eggs, chicken, tacos.", "Make it", "", 0),
    ]),
    ("buy", "Sauces to buy", "市販ソース", "Ready-made and light. Check the label for kcal per 15 ml.", [
        ("Ponzu", "ポン酢", 8, "1 tbsp", "Citrus soy for almost anything: tofu, fish, salads.", "Supermarket", "soy, wheat", 250),
        ("Non-oil dressing", "ノンオイルドレッシング", 12, "1 tbsp", "Sesame-free 'aojiso' or onion flavours are the lightest.", "Supermarket", "soy, wheat", 250),
        ("Half-calorie mayo", "カロリーハーフマヨ", 45, "1 tbsp", "Half the fat of regular mayo. Thin it with lemon.", "Supermarket", "egg", 300),
        ("Low-sugar ketchup", "糖質オフケチャップ", 10, "1 tbsp", "For omurice and eggs without the sugar.", "Supermarket", "", 300),
        ("Shirodashi", "白だし", 10, "1 tbsp", "Clear dashi seasoning: soups, tamagoyaki, udon, quick pickles.", "Supermarket", "soy, wheat, fish", 350),
        ("Mentsuyu", "めんつゆ", 15, "1 tbsp", "Noodle base, also a 1-bottle sauce for oyakodon and nimono.", "Supermarket", "soy, wheat, fish", 300),
        ("Sriracha", "シラチャー", 5, "1 tsp", "Garlic chili heat for eggs, rice, noodles.", "Kaldi", "", 400),
        ("Tabasco", "タバスコ", 1, "1 tsp", "Sharp vinegar heat for basically zero.", "Supermarket", "", 300),
        ("Fish sauce", "ナンプラー", 5, "1 tsp", "Salty umami for stir-fries and Thai-style salads.", "Supermarket", "fish", 300),
    ]),
    ("spice", "Spices & blends", "スパイス", "Almost no calories. The cheapest way to not get bored.", [
        ("Shichimi togarashi", "七味唐辛子", 2, "1 tsp", "On udon, miso soup, grilled chicken.", "Supermarket", "sesame", 150),
        ("Sansho pepper", "山椒", 2, "pinch", "Lemony tingle for eel-style chicken and mapo tofu.", "Supermarket", "", 200),
        ("Smoked paprika", "スモークパプリカ", 6, "1 tsp", "Smoky flavour for chicken breast and eggs.", "Kaldi", "", 400),
        ("Garlic powder", "ガーリックパウダー", 10, "1 tsp", "Easy garlic for marinades and popcorn.", "Supermarket", "", 250),
        ("Cumin", "クミン", 8, "1 tsp", "Warm and earthy: beef, beans, curry.", "Supermarket", "", 300),
        ("Garam masala", "ガラムマサラ", 6, "1 tsp", "Stir in at the end of a curry for a 'restaurant' smell.", "Supermarket", "", 350),
        ("Gochugaru", "韓国唐辛子", 6, "1 tsp", "Fruity Korean chili flakes for kimchi-style anything.", "Gyomu Super", "", 400),
        ("Magic salt", "マジックソルト", 0, "pinch", "Garlic-herb salt for steak, chicken, veg.", "Supermarket", "", 250),
        ("Dashi powder", "顆粒だし", 2, "1 tsp", "Instant umami for soups, eggs, veg.", "Supermarket", "fish", 250),
        ("Za'atar", "ザアタル", 10, "1 tsp", "Thyme + sumac + sesame. On yogurt, eggs, toast.", "Kaldi", "sesame", 500),
        ("Cajun seasoning", "ケイジャンスパイス", 5, "1 tsp", "Bold rub for chicken breast and potatoes.", "Kaldi", "", 400),
        ("Nori furikake", "のりふりかけ", 10, "1 tsp", "Pick a nori/salmon one, skip the sugary kids' kind.", "Supermarket", "sesame, fish", 150),
    ]),
    ("curry", "Curry, the lighter way", "カレー", "One block of normal roux is about 100 kcal, mostly fat. Ways around it:", [
        ("Curry flakes", "カレーフレーク", 60, "15 g", "Flakes portion more easily than blocks: use a measured spoon.", "Supermarket", "wheat", 400),
        ("Fat-reduced roux", "カロリー控えめルウ", 60, "1 block", "Boxes marked カロリーハーフ or 脂質オフ. Check the label.", "Supermarket", "wheat, soy", 300),
        ("Half-roux trick", "ルウ半分", 50, "1 serving", "Half the blocks + 1 tsp curry powder + grated onion or apple.", "Make it", "wheat", 0),
        ("Powder-only curry", "カレー粉カレー", 40, "1 serving", "Curry powder + canned tomato + onion + stock, thicken with starch.", "Make it", "", 0),
        ("Light retort curry", "低カロリーレトルトカレー", 100, "1 pack", "Calorie-controlled packs, around 100 kcal. Add your own chicken.", "Supermarket", "wheat", 200),
        ("Thai curry paste", "タイカレーペースト", 15, "1 tbsp", "Paste + milk or light coconut milk instead of a full can.", "Kaldi", "fish, shellfish", 350),
    ]),
    ("fancy", "Fancy upgrades", "ちょっと贅沢", "A bit special, still light.", [
        ("Shio koji", "塩麹", 10, "1 tsp", "Marinate chicken breast overnight: juicy and tender.", "Supermarket", "", 300),
        ("Yuzu kosho", "柚子胡椒", 3, "1/2 tsp", "Citrus chili paste for steak, hot pot, sashimi.", "Supermarket", "", 400),
        ("Black vinegar", "黒酢", 5, "1 tbsp", "Rich and mellow: dumplings, stir-fries, sweet-sour pork.", "Supermarket", "", 400),
        ("Bonito flakes", "かつお節", 10, "1 pack", "Umami and a bit of protein on tofu, rice, okonomiyaki.", "Supermarket", "fish", 250),
        ("Nutritional yeast", "ニュートリショナルイースト", 20, "1 tbsp", "Cheesy taste with protein. On popcorn, eggs, pasta.", "Online", "", 1200),
        ("Harissa", "ハリッサ", 15, "1 tsp", "North African chili paste for eggs, yogurt, roast veg.", "Kaldi", "", 500),
        ("Shiso leaves", "大葉", 0, "5 leaves", "Fresh mint-basil taste. Wrap pork or chicken, top pasta.", "Supermarket", "", 100),
        ("Cilantro", "パクチー", 2, "a handful", "For Thai, Mexican and Vietnamese bowls.", "Supermarket", "", 150),
        ("Truffle salt", "トリュフ塩", 0, "pinch", "Restaurant smell on eggs, fries, mushrooms.", "Kaldi", "", 800),
    ]),
]
