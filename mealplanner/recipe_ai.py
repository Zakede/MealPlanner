"""Recipe ideas from a model, checked and recomputed by our own code before anything is saved."""
from . import store
from .costing import per_serving, recipe_totals

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")
MAX_INGREDIENTS = 15
MAX_STEPS = 15


def build_prompt(request_text, foods, s, kcal_hint, protein_hint, expiring):
    food_names = "\n".join(f"- {f['name']}" for f in foods)
    allergies = s["allergies"] or "none"
    dislikes = s["dislikes"] or "none"
    expiring_line = ", ".join(expiring) if expiring else "nothing in particular"
    return f"""You write simple, tasty, high-protein home recipes for one person living in Japan.

Request: {request_text or "any meal"}

Rules:
- Use ONLY ingredients from the list below, spelled exactly as written. If something is missing, leave it out.
- Grams are for the whole recipe. Keep it simple: at most {MAX_INGREDIENTS} ingredients and {MAX_STEPS} steps.
- Never use these (allergies): {allergies}. Avoid: {dislikes}. Spice level 0-5, max {s["spice_tolerance"]}.
- Aim for about {kcal_hint} kcal and {protein_hint} g protein per serving. Prefer lean protein and vegetables.
- Try to use these, they expire soon: {expiring_line}.
- Steps must include safe cooking (e.g. cook chicken through) and use plain, short sentences.

Ingredients you may use:
{food_names}

Reply with ONE JSON object and nothing else, in this shape:
{{"name": "...", "servings": 1, "active_min": 10, "total_min": 15,
  "meal_types": ["lunch", "dinner"], "tags": ["spicy", "crunchy"], "cuisine": "japanese",
  "spice_level": 1, "portable": false, "batch_ok": false,
  "ingredients": [{{"food": "Chicken breast", "grams": 150}}],
  "steps": ["...", "..."]}}
"""


def _int(value, lo, hi, default):
    try:
        return max(lo, min(hi, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def validate(data, s):
    """Turn a model reply into a recipe we trust. Returns (recipe or None, problems, warnings).

    Problems block saving; warnings are shown but allowed.
    """
    problems, warnings = [], []
    if not isinstance(data, dict):
        return None, ["the reply was not a recipe"], []

    name = str(data.get("name") or "").strip()[:80]
    if not name:
        problems.append("missing a name")
    servings = _int(data.get("servings"), 1, 8, 1)
    active = _int(data.get("active_min"), 0, 180, 15)
    total = max(active, _int(data.get("total_min"), 0, 600, active))

    allergies = store.split_list(s["allergies"])
    dislikes = store.split_list(s["dislikes"])
    ingredients, dropped = [], []
    raw_ings = data.get("ingredients") if isinstance(data.get("ingredients"), list) else []
    for item in raw_ings[:MAX_INGREDIENTS]:
        if not isinstance(item, dict):
            continue
        food = store.food_by_name(str(item.get("food") or ""))
        grams = _int(item.get("grams"), 0, 3000, 0)
        if not food:
            dropped.append(str(item.get("food") or "?"))
            continue
        if grams <= 0:
            warnings.append(f"{food['name']} had no amount and was left out")
            continue
        lowered = food["name"].lower()
        food_allergens = store.split_list(food["allergens"])
        hit = [a for a in allergies if a in food_allergens or a in lowered]
        if hit:
            problems.append(f"{food['name']} contains {', '.join(hit)}, which is on your allergy list")
        if any(d in lowered for d in dislikes):
            problems.append(f"{food['name']} is on your dislike list")
        ing = dict(food)
        ing["grams"] = grams
        ing["price_per_100g"] = food["current_price"]
        ingredients.append(ing)
    if dropped:
        warnings.append("Left out (not in your food catalogue): " + ", ".join(dropped))
    if not ingredients:
        problems.append("no usable ingredients")

    steps = [str(x).strip() for x in (data.get("steps") or []) if str(x).strip()][:MAX_STEPS] \
        if isinstance(data.get("steps"), list) else []
    if not steps:
        problems.append("no steps")

    spice = _int(data.get("spice_level"), 0, 5, 0)
    if spice > s["spice_tolerance"]:
        warnings.append(f"Spice {spice} is above your tolerance of {s['spice_tolerance']}")

    types = [t for t in (data.get("meal_types") or []) if t in MEAL_TYPES] if isinstance(data.get("meal_types"), list) else []
    tags = [str(t).strip().lower()[:20] for t in (data.get("tags") or []) if str(t).strip()][:6] \
        if isinstance(data.get("tags"), list) else []

    recipe = {
        "name": name, "servings": servings, "active_min": active, "total_min": total,
        "meal_types": ",".join(types or ["lunch", "dinner"]), "tags": ",".join(tags),
        "cuisine": str(data.get("cuisine") or "").strip().lower()[:20], "spice_level": spice,
        "portable": 1 if data.get("portable") is True else 0, "batch_ok": 1 if data.get("batch_ok") is True else 0,
        "thaw_hours": 0, "fridge_days": 3, "steps": "\n".join(steps), "ingredients": ingredients,
    }
    if ingredients:
        # our own arithmetic, never the model's
        recipe["per_serving"] = per_serving(recipe_totals(ingredients), servings)
        kcal = recipe["per_serving"]["kcal"]
        if not 120 <= kcal <= 1400:
            warnings.append(f"{round(kcal)} kcal per serving is unusual. Check the amounts")
    return recipe, problems, warnings


def to_form(recipe):
    """Shape a checked recipe like the recipe form, so the normal save path is reused."""
    form = {k: str(recipe[k]) for k in ("name", "active_min", "total_min", "servings", "spice_level",
                                         "thaw_hours", "fridge_days", "tags", "cuisine", "steps")}
    for t in recipe["meal_types"].split(","):
        form[f"type_{t}"] = "on"
    if recipe["batch_ok"]:
        form["batch_ok"] = "on"
    if recipe["portable"]:
        form["portable"] = "on"
    return form, [(i["name"], str(i["grams"])) for i in recipe["ingredients"]]


def build_import_prompt(source_text, foods, s):
    food_names = "\n".join(f"- {f['name']}" for f in foods)
    return f"""Turn the recipe below into a simple home recipe for one person in Japan.

Rules:
- Map every ingredient to the closest item in the list below, spelled exactly as written.
  Leave out salt, pepper, water and anything with no close match.
- Convert cups, spoons and pieces into grams for the whole recipe.
- Keep the original idea and flavour. Make it a little lighter if it is very oily or sugary.
- Never use these (allergies): {s["allergies"] or "none"}.
- Steps: short, plain sentences with clear doneness cues.

Recipe:
\"\"\"
{source_text[:6000]}
\"\"\"

Ingredients you may use:
{food_names}

Reply with ONE JSON object and nothing else, in this shape:
{{"name": "...", "servings": 1, "active_min": 10, "total_min": 15,
  "meal_types": ["lunch", "dinner"], "tags": ["garlicky"], "cuisine": "korean",
  "spice_level": 1, "portable": false, "batch_ok": false,
  "ingredients": [{{"food": "Chicken breast", "grams": 150}}],
  "steps": ["...", "..."]}}
"""


def recipe_from_jsonld(html):
    """Pull a schema.org Recipe out of a web page, as plain text for the model. None if absent."""
    import json
    import re
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if "@graph" in item:
                    stack.extend(item["@graph"])
                kind = item.get("@type")
                if kind == "Recipe" or (isinstance(kind, list) and "Recipe" in kind):
                    steps = item.get("recipeInstructions") or []
                    if isinstance(steps, list):
                        steps = [x.get("text", "") if isinstance(x, dict) else str(x) for x in steps]
                    else:
                        steps = [str(steps)]
                    return "\n".join([str(item.get("name", "")), f"Serves: {item.get('recipeYield', '')}",
                                      "Ingredients:", *map(str, item.get("recipeIngredient") or []),
                                      "Steps:", *steps])
    return None


def page_text(html):
    """Rough visible text of a page, for pages without structured recipe data."""
    import re
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()[:6000]


def fetch_url(url, timeout=10, max_bytes=2_000_000):
    """Download a page for import. Only http(s); errors become ValueError."""
    from urllib.parse import urlparse
    from urllib.request import Request, urlopen
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("only http and https links work")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (meal planner recipe import)"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes)
            charset = resp.headers.get_content_charset() or "utf-8"
    except Exception as e:  # network errors come in many types
        raise ValueError(f"couldn't open the link ({e.__class__.__name__})")
    return raw.decode(charset, errors="replace")
