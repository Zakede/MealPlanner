"""'Ask Zettai': short AI answers to any food question, shaped to the user's diet, day and pantry."""

KINDS = ("dish", "swap", "sauce", "spice", "flavour", "tip")
STARTERS = [
    "What can I make with what's in my pantry?",
    "I've run out of an ingredient for tonight's dinner. What can I use instead?",
    "What should I eat before a long shift?",
    "How long do cooked leftovers keep in the fridge?",
    "A new dish I've never tried",
    "Make chicken breast less boring",
    "Something from a cuisine I don't usually eat",
    "A cheap high-protein dinner",
    "A spice blend for roast vegetables",
    "A light sauce for rice bowls",
]


def build_prompt(question, s, country, today=""):
    return f"""You help someone eat well: high protein, sensible calories, on a budget, shopping in {country}.
Answer their food question. A direct question (food safety, nutrition, how to cook or store something,
what to eat today) gets a direct answer of up to 4 short sentences, plus ideas only if they help.
A request for ideas gets 3 to 5 short, practical ideas. Food safety: be careful and clear, never guess.
If the question isn't about food, eating, cooking or shopping for food, say so kindly in the answer.
Missing or run-out ingredients: suggest swaps from what's in their kitchen first, then cheap things to buy,
say how much to use and how it changes the dish (taste, kcal, protein). Use kind "swap" for those.
When one of their own dishes fits, name it exactly as listed.

About them:
- Diet: {s.get("diet") or "anything"}. Allergies (never suggest): {s.get("allergies") or "none"}.
- Won't eat: {s.get("dislikes") or "nothing listed"}. Spice tolerance {s.get("spice_tolerance", 2)}/5.
- Likes: {s.get("flavor_likes") or "not said"}; cuisines: {s.get("cuisines_liked") or "not said"}.
{today}

Question: \"\"\"{question[:300]}\"\"\"

Rules: plain English, no Japanese script. Each idea is something they can actually buy or cook at home.
Keep every text field under 25 words.

Reply with ONE JSON object and nothing else:
{{"answer": "the direct answer, or one friendly sentence", "ideas": [
  {{"kind": "dish|sauce|spice|flavour|tip", "name": "...", "what": "what it is / how to make it",
    "why": "why it fits them", "kcal": 0}}]}}
"""


def clean(data):
    """Keep only well-formed ideas; numbers become ints. Returns (answer, ideas)."""
    if not isinstance(data, dict):
        return "", []
    ideas = []
    for i in (data.get("ideas") or [])[:6]:
        if not isinstance(i, dict) or not str(i.get("name") or "").strip():
            continue
        kind = str(i.get("kind") or "tip").lower()
        try:
            kcal = max(0, min(2000, int(float(i.get("kcal") or 0))))
        except (TypeError, ValueError):
            kcal = 0
        ideas.append({"kind": kind if kind in KINDS else "tip", "name": str(i["name"]).strip()[:60],
                      "what": str(i.get("what") or "").strip()[:200], "why": str(i.get("why") or "").strip()[:160],
                      "kcal": kcal})
    return str(data.get("answer") or "").strip()[:600], ideas


STOP_WORDS = {"with", "and", "the", "for", "from", "bowl", "rice", "salad", "style", "easy", "quick"}


def _words(text):
    return {w for w in "".join(c if c.isalnum() else " " for c in text.lower()).split() if len(w) > 3}


def mentioned(question, recipes):
    """Their dishes the question talks about: the full name, or two telling words of it."""
    q, qw = question.lower(), _words(question)
    hits = []
    for r in recipes:
        name = r["name"].lower()
        telling = _words(name) - STOP_WORDS
        if name in q or len(telling & qw) >= min(2, len(telling)) and telling & qw:
            hits.append(r)
    return hits


def recipe_context(question, recipes, upcoming, have_g, at_home):
    """Their dish list, plus the ingredients of dishes asked about or coming up, marked have / short / missing."""
    lines = ["- Their dishes: " + ", ".join(r["name"] for r in recipes[:120]) + "."]
    detail, seen = [], set()
    for r, when in [(r, "asked about") for r in mentioned(question, recipes)] + upcoming:
        if r["id"] in seen or len(detail) >= 4:
            continue
        seen.add(r["id"])
        parts = []
        for ing in r["ingredients"]:
            need, got = ing["grams"], have_g.get(ing["id"], 0)
            if ing["name"].lower() in at_home or got >= need * 0.9:
                state = "have"
            elif got > 0:
                state = f"only {round(got)} g"
            else:
                state = "MISSING"
            parts.append(f"{ing['name']} {round(need)} g ({state})")
        detail.append(f"- {r['name']} ({when}): " + "; ".join(parts))
    return "\n".join(lines + detail)


def today_context(kcal_left, protein_left, pantry, activities):
    """A few lines about their day so answers like 'what should I eat now' fit."""
    lines = [f"- Today: about {kcal_left} kcal and {protein_left} g protein left to eat."]
    if activities:
        lines.append("- Today's activities: " + ", ".join(activities) + ".")
    if pantry:
        lines.append("- In their kitchen now (soonest to expire first): " + ", ".join(pantry[:25]) + ".")
    return "\n".join(lines)
