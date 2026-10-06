"""Kitchen staples: what you actually use (garlic powder for fresh garlic, spray for oil), and what's always at home.

A swap here changes every recipe as it's loaded: the ingredient, its amount, calories and cost. Staples marked
"always at home" never land on the shopping list.
"""
import json

# original food -> [(substitute food, grams of substitute per gram of original, how much in kitchen words)]
STAPLES = {
    "Garlic": [("Grated garlic (tube)", 1.0, "1 cm of tube per clove"), ("Garlic powder", 0.2, "1/4 tsp per clove")],
    "Ginger": [("Ginger paste (tube)", 1.0, "same amount"), ("Ground ginger", 0.15, "a pinch per slice")],
    "Green onion": [("Dried green onion", 0.15, "a small pinch")],
    "Onion": [("Onion powder", 0.1, "1 tsp per half onion")],
    "Olive oil": [("Vegetable oil", 1.0, "same amount"), ("Cooking spray", 0.3, "a 1-second spray, far fewer kcal")],
    "Sesame oil": [("Olive oil", 1.0, "same amount, less sesame taste"), ("Vegetable oil", 1.0, "same amount")],
    "Honey": [("Monk fruit sweetener", 0.6, "zero calories")],
    "Soy sauce": [("Low-sodium soy sauce", 1.0, "same amount, less salt")],
    "Cooked rice": [("Microwave rice pack", 1.0, "no rice cooker needed")],
}
# no swap offered, but worth saying "I always have this"
BASICS = ["Mirin", "Miso", "Oyster sauce", "Curry powder", "Gochujang", "Ponzu", "Chili crisp", "Chili bean paste",
          "Half-calorie mayo", "Lemon juice", "Taco spice mix"]


def load(settings):
    try:
        raw = json.loads(settings.get("staples") or "{}")
    except (TypeError, ValueError):
        return {}
    out = {}
    for name, v in raw.items():
        if name not in STAPLES and name not in BASICS:
            continue
        use = v.get("use") if v.get("use") in {s for s, _, _ in STAPLES.get(name, [])} else None
        out[name] = {"use": use, "have": bool(v.get("have"))}
    return out


def from_form(form):
    out = {}
    for name in list(STAPLES) + BASICS:
        key = name.lower().replace(" ", "_")
        use = form.get(f"use_{key}") or None
        have = bool(form.get(f"have_{key}"))
        if use or have:
            out[name] = {"use": use, "have": have}
    return json.dumps(out, sort_keys=True)


def swap_for(name, prefs):
    """(substitute name, ratio, note) chosen for this food, or None."""
    use = (prefs.get(name) or {}).get("use")
    for sub, ratio, note in STAPLES.get(name, []):
        if sub == use:
            return sub, ratio, note
    return None


def at_home(prefs):
    """Lower-case names of foods you always have: the staple itself, or what you use instead."""
    out = set()
    for name, v in prefs.items():
        if v.get("have"):
            out.add((v.get("use") or name).lower())
    return out
