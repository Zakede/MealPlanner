"""'Ask Zettai': short AI answers about new dishes, flavours, sauces and spices, shaped to the user's diet."""

KINDS = ("dish", "sauce", "spice", "flavour", "tip")
STARTERS = [
    "A new dish I've never tried",
    "Make chicken breast less boring",
    "Something from a cuisine I don't usually eat",
    "A cheap high-protein dinner",
    "A spice blend for roast vegetables",
    "A light sauce for rice bowls",
]


def build_prompt(question, s, country):
    return f"""You help someone eat well: high protein, sensible calories, on a budget, shopping in {country}.
Answer their food question with 3 to 5 short, practical ideas.

About them:
- Diet: {s.get("diet") or "anything"}. Allergies (never suggest): {s.get("allergies") or "none"}.
- Won't eat: {s.get("dislikes") or "nothing listed"}. Spice tolerance {s.get("spice_tolerance", 2)}/5.
- Likes: {s.get("flavor_likes") or "not said"}; cuisines: {s.get("cuisines_liked") or "not said"}.

Question: \"\"\"{question[:300]}\"\"\"

Rules: plain English, no Japanese script. Each idea is something they can actually buy or cook at home.
Keep every text field under 25 words.

Reply with ONE JSON object and nothing else:
{{"answer": "one friendly sentence", "ideas": [
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
    return str(data.get("answer") or "").strip()[:200], ideas
