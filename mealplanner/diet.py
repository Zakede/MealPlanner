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

# Quick "I don't eat this" toggles. Each matches categories or words in food names.
AVOID_OPTIONS = {
    "fish": ("Fish", {"fish"}, ()),
    "seafood": ("Shellfish & shrimp", {"seafood"}, ()),
    "pork": ("Pork", set(), ("pork",)),
    "beef": ("Beef", set(), ("beef",)),
    "dairy": ("Dairy", {"dairy"}, ()),
    "egg": ("Eggs", {"egg"}, ()),
    "soy": ("Soy & tofu", {"soy"}, ("tofu", "natto", "atsuage")),
    "spicy": ("Spicy food", set(), ()),
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
        _, cats_out, words = AVOID_OPTIONS.get(key, ("", set(), ()))
        if cats & cats_out or any(w in n for w in words for n in names):
            return False
    return True


def bonus(recipe, diet):
    if diet == "high_meat" and categories(recipe) & {"poultry", "meat"}:
        return 0.15
    return 0.0
