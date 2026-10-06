"""Small data-access helpers shared by the views and the planner."""
from .db import query
from .nutrition import compute_targets


def settings():
    return dict(query("SELECT * FROM settings WHERE id = 1", one=True))


def profile_complete(s):
    return s["age"] is not None and s["sex"] in ("male", "female")


def targets(s=None):
    """Daily targets, or None while age/sex are still missing."""
    s = s or settings()
    if not profile_complete(s):
        return None
    return compute_targets(
        weight_kg=s["weight_kg"],
        height_cm=s["height_cm"],
        age=s["age"],
        sex=s["sex"],
        activity=s["activity"],
        pace_kg_week=s["pace_kg_week"],
        goal_weight_kg=s["goal_weight_kg"],
    )


def split_list(text):
    return [part.strip().lower() for part in (text or "").split(",") if part.strip()]
