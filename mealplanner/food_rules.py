"""How you like each protein: love it, fine, only from the air fryer, a little, or never.

Finer than the dislike list, which is all-or-nothing: "chicken, but only air-fried" is a rule here.
"""
import json

from .equipment import needs

GROUPS = {
    "chicken": "Chicken",
    "pork": "Pork",
    "beef": "Beef",
    "fish": "Fish",
    "seafood": "Shrimp & squid",
    "eggs": "Eggs",
    "tofu": "Tofu & soy",
}
RULES = {
    "love": ("Love it", "More often"),
    "any": ("Fine", "No rule"),
    "airfryer": ("Air fryer only", "Only air-fried recipes"),
    "small": ("A little", "Small amounts"),
    "never": ("Never", "Not at all"),
}
SMALL_GRAMS = 40


def groups_of(ingredient):
    """Which protein groups one ingredient belongs to (mixed mince is both pork and beef)."""
    name, cat = ingredient["name"].lower(), ingredient.get("category") or ""
    out = set()
    if cat == "poultry" or "chicken" in name:
        out.add("chicken")
    if "pork" in name or "mixed mince" in name or "bacon" in name or name == "ham" or name.startswith("ham "):
        out.add("pork")
    if "beef" in name or "mixed mince" in name:
        out.add("beef")
    if cat == "fish":
        out.add("fish")
    if cat == "seafood":
        out.add("seafood")
    if cat == "egg":
        out.add("eggs")
    if cat == "soy" and "soy sauce" not in name and "milk" not in name:
        out.add("tofu")
    return out


def load(settings):
    try:
        rules = json.loads(settings.get("food_rules") or "{}")
    except (TypeError, ValueError):
        return {}
    return {g: r for g, r in rules.items() if g in GROUPS and r in RULES and r != "any"}


def dump(rules):
    return json.dumps({g: r for g, r in rules.items() if g in GROUPS and r in RULES and r != "any"}, sort_keys=True)


def recipe_groups(recipe):
    """{group: grams per serving} for the proteins in a recipe."""
    servings = max(1, recipe.get("servings") or 1)
    out = {}
    for ing in recipe["ingredients"]:
        for g in groups_of(ing):
            out[g] = out.get(g, 0) + ing["grams"] / servings
    return out


def breaks(recipe, rules):
    """True when a recipe goes against a rule: a 'never' protein, or an 'air fryer only' one cooked another way."""
    if not rules:
        return False
    used = recipe_groups(recipe)
    for g in used:
        rule = rules.get(g)
        if rule == "never":
            return True
        if rule == "airfryer" and "air_fryer" not in needs(recipe):
            return True
    return False


def bonus(recipe, rules):
    """Score nudge: loved proteins up, 'a little' ones down when the portion is big."""
    if not rules:
        return 0.0
    total = 0.0
    for g, grams in recipe_groups(recipe).items():
        rule = rules.get(g)
        if rule == "love":
            total += 0.08
        elif rule == "airfryer":
            total += 0.04        # you asked for these: let them come up
        elif rule == "small" and grams > SMALL_GRAMS:
            total -= 0.15
    return total


def from_form(form):
    """{group: rule} from fields named rule_<group>."""
    return {g: form.get(f"rule_{g}") for g in GROUPS if form.get(f"rule_{g}") in RULES}
