"""Body targets: BMR, TDEE, calorie and macro goals.

Everything here is plain arithmetic with no database access so it can be
unit tested directly.
"""
from dataclasses import dataclass

KCAL_PER_KG = 7700          # approx. energy in 1 kg of body fat
MAX_PACE_KG_WEEK = 0.75
CALORIE_FLOOR = {"male": 1500, "female": 1200}
PROTEIN_G_PER_KG = 1.8
FAT_SHARE = 0.25            # share of calories from fat
MIN_FAT_G_PER_KG = 0.6
GYM_DAY_EXTRA_KCAL = 150
GYM_DAY_EXTRA_PROTEIN = 20

ACTIVITY_LEVELS = {
    "sedentary": (1.2, "Desk job, little exercise"),
    "light": (1.375, "Light exercise 1-3 days a week"),
    "moderate": (1.55, "Exercise 3-5 days a week"),
    "active": (1.725, "Hard exercise 6-7 days a week"),
    "very_active": (1.9, "Physical job plus training"),
}


# Daily life, without training.
JOB_LEVELS = {
    "desk": (1.2, "Desk job or studying", "Sitting most of the day"),
    "standing": (1.35, "On your feet", "Retail, teaching, waiting tables"),
    "physical": (1.5, "Physical job", "Construction, warehouse, moving"),
}
# Extra multiplier per training day a week.
TRAINING_LEVELS = {
    "light": (0.025, "Light", "Walks, easy cycling, light weights"),
    "moderate": (0.035, "Moderate", "Normal gym sessions"),
    "hard": (0.05, "Hard", "Heavy lifting, sports, HIIT"),
}


def activity_multiplier(job, training_days, intensity):
    base = JOB_LEVELS.get(job, JOB_LEVELS["desk"])[0]
    per_day = TRAINING_LEVELS.get(intensity, TRAINING_LEVELS["moderate"])[0]
    return round(min(2.0, base + per_day * max(0, min(7, training_days))), 3)


def bmr_mifflin(weight_kg, height_cm, age, sex):
    """Mifflin-St Jeor resting energy in kcal/day."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if sex == "male":
        return base + 5
    if sex == "female":
        return base - 161
    raise ValueError(f"sex must be 'male' or 'female', got {sex!r}")


def tdee(bmr, activity):
    """activity is a named level or a multiplier."""
    mult = activity if isinstance(activity, (int, float)) else ACTIVITY_LEVELS[activity][0]
    return bmr * mult


def clamp_pace(pace_kg_week, weight_kg, goal_weight_kg):
    """Never lose faster than MAX_PACE_KG_WEEK, and stop at the goal."""
    if weight_kg <= goal_weight_kg:
        return 0.0
    return max(0.0, min(pace_kg_week, MAX_PACE_KG_WEEK))


@dataclass
class Targets:
    bmr: int
    tdee: int
    kcal: int
    protein_g: int
    fat_g: int
    carbs_g: int
    pace_requested: float
    pace_effective: float
    pace_capped: bool
    floor_applied: bool
    weeks_to_goal: float | None


def macro_split(kcal, protein_g, weight_kg):
    fat_g = max(kcal * FAT_SHARE / 9, MIN_FAT_G_PER_KG * weight_kg)
    carbs_g = max(0.0, (kcal - protein_g * 4 - fat_g * 9) / 4)
    return round(fat_g), round(carbs_g)


def compute_targets(weight_kg, height_cm, age, sex, activity, pace_kg_week, goal_weight_kg):
    bmr = bmr_mifflin(weight_kg, height_cm, age, sex)
    maintenance = tdee(bmr, activity)
    pace = clamp_pace(pace_kg_week, weight_kg, goal_weight_kg)
    daily_deficit = pace * KCAL_PER_KG / 7

    floor = CALORIE_FLOOR[sex]
    kcal = maintenance - daily_deficit
    floor_applied = kcal < floor
    kcal = max(kcal, floor)
    kcal = int(round(kcal / 10) * 10)

    # the floor can make the real pace slower than the requested one
    effective = max(0.0, (maintenance - kcal) * 7 / KCAL_PER_KG)
    protein = round(PROTEIN_G_PER_KG * weight_kg)
    fat, carbs = macro_split(kcal, protein, weight_kg)

    to_lose = weight_kg - goal_weight_kg
    weeks = round(to_lose / effective, 1) if effective > 0 and to_lose > 0 else None

    return Targets(
        bmr=round(bmr),
        tdee=round(maintenance),
        kcal=kcal,
        protein_g=protein,
        fat_g=fat,
        carbs_g=carbs,
        pace_requested=pace_kg_week,
        pace_effective=round(effective, 2),
        pace_capped=pace_kg_week > MAX_PACE_KG_WEEK,
        floor_applied=floor_applied,
        weeks_to_goal=weeks,
    )


def day_targets(targets, gym, gym_days_per_week, sex):
    """Shift calories toward gym days while keeping the weekly total the same.

    Returns (kcal, protein_g) for one day.
    """
    kcal, protein = targets.kcal, targets.protein_g
    if gym_days_per_week in (0, 7):
        return kcal, protein
    if gym:
        return kcal + GYM_DAY_EXTRA_KCAL, protein + GYM_DAY_EXTRA_PROTEIN
    rest_days = 7 - gym_days_per_week
    cut = GYM_DAY_EXTRA_KCAL * gym_days_per_week / rest_days
    return max(CALORIE_FLOOR[sex], round(kcal - cut)), protein


def kg_to_lb(kg):
    return kg * 2.20462


def lb_to_kg(lb):
    return lb / 2.20462


def cm_to_in(cm):
    return cm / 2.54


def in_to_cm(inches):
    return inches * 2.54
