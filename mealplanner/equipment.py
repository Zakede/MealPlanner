import re

"""Kitchen appliances, and which ones a recipe needs."""

APPLIANCES = {
    "stove": "Stove / hob",
    "microwave": "Microwave",
    "rice_cooker": "Rice cooker",
    "toaster_oven": "Toaster oven",
    "oven": "Full oven",
    "air_fryer": "Air fryer",
    "blender": "Blender",
    "freezer": "Freezer space",
}

STOVE_WORDS = ("fry", "pan", "simmer", "boil", "sear", "bring", "scramble", "grill", "toss", "bubble", "soften")
# whole words, so "panko" isn't a pan; "fry" also catches fried / fries / frying
STOVE_RE = re.compile(r"\b(?:fr(?:y|ies|ied|ying)|pans?|" + "|".join(w + r"\w*" for w in STOVE_WORDS[2:]) + r")\b")


def needs(recipe):
    """Appliances a recipe needs. A manual list on the recipe wins over guessing from the steps."""
    if recipe.get("equipment"):
        return {e for e in recipe["equipment"].split(",") if e}
    steps = recipe.get("steps", "").lower()
    out = set()
    # "air fry" is not frying on the stove
    stove_text = steps.replace("air fryer", "").replace("air fry", "").replace("air-fry", "")
    if STOVE_RE.search(stove_text):
        out.add("stove")
    if "microwave" in steps:
        out.add("microwave")
    if "toast" in steps:
        out.add("toaster_oven")
    if "air fry" in steps:
        out.add("air_fryer")
    if "blend" in steps:
        out.add("blender")
    if " oven" in steps and "toaster" not in steps:
        out.add("oven")
    return out


def can_make(recipe, have):
    """have: set of appliance keys. Rice can come from a rice cooker, a microwave pack or a pot."""
    need = needs(recipe)
    names = {i["name"] for i in recipe.get("ingredients", [])}
    if "Cooked rice" in names and not have & {"rice_cooker", "microwave", "stove"}:
        return False
    if "toaster_oven" in need and "oven" in have:
        need = need - {"toaster_oven"}
    if "microwave" in need and "stove" in have and "microwave" not in have:
        need = need - {"microwave"}  # anything microwaved can be heated in a pan
    return need <= have
