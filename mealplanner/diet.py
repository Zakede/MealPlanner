"""Diet styles and "things I avoid", checked against ingredient categories."""

DIETS = {
    "any": ("Anything", "No restrictions"),
    "high_meat": ("Meat lover", "Meat and chicken most days"),
    "pescatarian": ("Pescatarian", "Fish, no meat"),
    "vegetarian": ("Vegetarian", "Eggs and dairy, no meat or fish"),
    "vegan": ("Vegan", "Plants only"),
    "keto": ("Keto / low carb", "Under 20 g carbs a meal"),
}
EXCLUDED_CATEGORIES = {
    "pescatarian": {"poultry", "meat"},
    "vegetarian": {"poultry", "meat", "fish", "seafood"},
    "vegan": {"poultry", "meat", "fish", "seafood", "egg", "dairy"},
}
KETO_MAX_CARBS = 20

# Options that make no sense once a diet already rules them out (protein-rule groups and avoid keys).
NOT_EATEN = {
    "pescatarian": {"chicken", "pork", "beef"},
    "vegetarian": {"chicken", "pork", "beef", "fish", "seafood"},
    "vegan": {"chicken", "pork", "beef", "fish", "seafood", "eggs", "egg", "dairy"},
}


def hidden_by(key):
    """Diets under which an option is pointless, space-separated, for data-diet-hide."""
    return " ".join(d for d, keys in NOT_EATEN.items() if key in keys)

# Quick "I don't eat this" toggles: (label, categories, words in food names, allergen tags).
AVOID_OPTIONS = {
    "chicken": ("Chicken", {"poultry"}, (), ()),
    "pork": ("Pork", set(), ("pork",), ()),
    "beef": ("Beef", set(), ("beef",), ()),
    "fish": ("Fish", {"fish"}, (), ()),
    "seafood": ("Shellfish & shrimp", {"seafood"}, (), ("shellfish", "shrimp")),
    "dairy": ("Dairy", {"dairy"}, (), ("milk",)),
    "egg": ("Eggs", {"egg"}, (), ("egg",)),
    "soy": ("Soy & tofu", {"soy"}, ("tofu", "natto", "atsuage"), ("soy",)),
    "gluten": ("Wheat / gluten", set(), ("bread", "pasta", "udon", "panko"), ("wheat",)),
    "nuts": ("Peanuts & nuts", set(), ("peanut",), ("peanut",)),
    "sesame": ("Sesame", set(), ("sesame",), ("sesame",)),
    "mushroom": ("Mushrooms", set(), ("mushroom", "shimeji"), ()),
    "allium": ("Onion & garlic", set(), ("onion", "garlic"), ()),
    "tomato": ("Tomato", set(), ("tomato",), ()),
    "natto": ("Natto", set(), ("natto",), ()),
    "kimchi": ("Kimchi", set(), ("kimchi",), ()),
    "rice": ("Rice", set(), ("rice",), ()),
    "spicy": ("Spicy food", set(), (), ()),
}


def categories(recipe):
    return {ing.get("category") or "" for ing in recipe["ingredients"]}


def allowed(recipe, diet, avoid):
    """Hard filter for diet style and avoid toggles. avoid is a list of AVOID_OPTIONS keys."""
    cats = categories(recipe)
    if cats & EXCLUDED_CATEGORIES.get(diet, set()):
        return False
    if diet == "keto" and recipe["per_serving"]["carbs"] > KETO_MAX_CARBS:
        return False
    names = [ing["name"].lower() for ing in recipe["ingredients"]]
    for key in avoid:
        if key == "spicy":
            if recipe["spice_level"] >= 2:
                return False
            continue
        _, cats_out, words, tags = AVOID_OPTIONS.get(key, ("", set(), (), ()))
        if cats & cats_out or any(w in n for w in words for n in names):
            return False
        if tags and any(t in recipe.get("allergens", []) for t in tags):
            return False
    return True


def bonus(recipe, diet):
    if diet == "high_meat" and categories(recipe) & {"poultry", "meat"}:
        return 0.15
    return 0.0
