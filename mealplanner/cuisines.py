"""Cuisines people can love, like or skip, plus any they add themselves.

Stored in settings as comma lists: cuisines_loved, cuisines_liked, cuisines_tired, cuisines_custom.
"""
from . import store

ALL = [
    "japanese", "korean", "chinese", "sichuan", "thai", "vietnamese", "filipino", "indonesian", "malaysian",
    "indian", "sri lankan", "nepali", "middle eastern", "turkish", "persian", "lebanese", "mediterranean",
    "greek", "italian", "spanish", "french", "british", "nordic", "eastern european", "moroccan",
    "ethiopian", "west african", "caribbean", "mexican", "tex-mex", "peruvian", "brazilian", "american",
    "soul food", "cajun", "hawaiian", "western",
]
LEVELS = ("love", "like", "", "no")


def ratings(s):
    """{cuisine: 'love' | 'like' | 'no'} from settings."""
    out = {}
    for level, field in (("like", "cuisines_liked"), ("no", "cuisines_tired"), ("love", "cuisines_loved")):
        for c in store.split_list(s.get(field)):
            out[c.lower()] = level
    return out


def everything(s):
    """Built-in cuisines plus the user's own, loved ones first."""
    mine = [c.lower() for c in store.split_list(s.get("cuisines_custom")) if c.lower() not in ALL]
    r = ratings(s)
    order = {"love": 0, "like": 1, "": 2, "no": 3}
    return sorted(ALL + mine, key=lambda c: (order[r.get(c, "")], (ALL + mine).index(c)))


def from_form(form, s):
    """Settings values from the cuisine picker (cuisine_<name> = love/like/no) and an added cuisine."""
    custom = [c.lower() for c in store.split_list(s.get("cuisines_custom"))]
    new = (form.get("new_cuisine") or "").strip().lower()[:30]
    if new and new not in ALL and new not in custom:
        custom.append(new)
    names = ALL + custom
    picked = {c: form.get(f"cuisine_{c}", "") for c in names}
    if new:
        picked[new] = picked.get(new) or "like"
    return {
        "cuisines_loved": ",".join(c for c in names if picked.get(c) == "love"),
        "cuisines_liked": ",".join(c for c in names if picked.get(c) == "like"),
        "cuisines_tired": ",".join(c for c in names if picked.get(c) == "no"),
        "cuisines_custom": ",".join(custom),
    }
