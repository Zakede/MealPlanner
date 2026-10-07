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


# everyday walking on top of work and training: (multiplier added, label, hint)
WALKING_LEVELS = {
    "little": (0.0, "Not much", "Under 5,000 steps"),
    "some": (0.05, "Some", "5,000-10,000 steps"),
    "lots": (0.1, "Lots", "10,000+, walk everywhere"),
}


def activity_multiplier(job, training_days, intensity, walking="little"):
    base = JOB_LEVELS.get(job, JOB_LEVELS["desk"])[0]
    per_day = TRAINING_LEVELS.get(intensity, TRAINING_LEVELS["moderate"])[0]
    walk = WALKING_LEVELS.get(walking, WALKING_LEVELS["little"])[0]
    return round(min(2.0, base + walk + per_day * max(0, min(7, training_days))), 3)


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


MAX_DEFICIT = round(MAX_PACE_KG_WEEK * KCAL_PER_KG / 7)   # 825 kcal/day


def macro_split(kcal, protein_g, weight_kg, fat_share=FAT_SHARE):
    fat_g = max(kcal * fat_share / 9, MIN_FAT_G_PER_KG * weight_kg)
    carbs_g = max(0.0, (kcal - protein_g * 4 - fat_g * 9) / 4)
    return round(fat_g), round(carbs_g)


def compute_targets(weight_kg, height_cm, age, sex, activity, pace_kg_week, goal_weight_kg,
                    deficit_kcal=None, protein_per_kg=PROTEIN_G_PER_KG, fat_share=FAT_SHARE):
    """deficit_kcal, when given, is used instead of the pace (still capped at the safe maximum)."""
    bmr = bmr_mifflin(weight_kg, height_cm, age, sex)
    maintenance = tdee(bmr, activity)
    if deficit_kcal is not None:
        requested = deficit_kcal * 7 / KCAL_PER_KG
        pace = clamp_pace(requested, weight_kg, goal_weight_kg)
        pace_kg_week = requested
    else:
        pace = clamp_pace(pace_kg_week, weight_kg, goal_weight_kg)
    daily_deficit = pace * KCAL_PER_KG / 7

    floor = CALORIE_FLOOR[sex]
    kcal = maintenance - daily_deficit
    floor_applied = kcal < floor
    kcal = max(kcal, floor)
    kcal = int(round(kcal / 10) * 10)

    # the floor can make the real pace slower than the requested one
    effective = max(0.0, (maintenance - kcal) * 7 / KCAL_PER_KG)
    protein_per_kg = max(1.2, min(2.6, protein_per_kg))
    fat_share = max(0.2, min(0.4, fat_share))
    protein = round(protein_per_kg * weight_kg)
    fat, carbs = macro_split(kcal, protein, weight_kg, fat_share)

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
        pace_capped=pace_kg_week > MAX_PACE_KG_WEEK + 1e-9,
        floor_applied=floor_applied,
        weeks_to_goal=weeks,
    )


HARD_DAY_HOURS = 10
HARD_DAY_SNACK = 150
HARD_DAY_PROTEIN = 10


# Rough METs (energy vs. sitting still) for a stretch of each kind of activity.
ACTIVITY_METS = {"desk": 1.5, "standing": 2.5, "physical": 3.5}
GYM_MET = 5.0


def activity_burn(bmr, intensity, hours, kind=None):
    """About how many kcal an activity burns on top of resting, for showing next to it."""
    if not bmr or hours <= 0:
        return 0
    met = GYM_MET if kind == "gym" else ACTIVITY_METS.get(intensity, ACTIVITY_METS["desk"])
    return int(round(bmr / 24 * min(hours, 16) * (met - 1) / 10) * 10)


def work_extra(bmr, base_job, day_job, hours):
    """Extra kcal for a workday that's more active than your usual job (or less, for a lighter day)."""
    if not day_job or day_job not in JOB_LEVELS or hours <= 0:
        return 0
    base = ACTIVITY_METS.get(base_job, ACTIVITY_METS["desk"])
    return round(bmr / 24 * min(hours, 12) * (ACTIVITY_METS[day_job] - base))


def is_hard_day(day_job, hours):
    return day_job == "physical" or hours >= HARD_DAY_HOURS


def work_blocks(work):
    """[(job, hours)] from either {"blocks": [...]} or the single {"job", "hours"} form."""
    if not work:
        return []
    if "blocks" in work:
        return [(j, h) for j, h in work["blocks"] if j and h > 0]
    return [(work.get("job"), work.get("hours", 0))] if work.get("job") else []


def is_hard(work):
    parts = work_blocks(work)
    return any(j == "physical" for j, _ in parts) or sum(h for _, h in parts) >= HARD_DAY_HOURS


def day_targets(targets, gym, gym_days_per_week, sex, work=None):
    """Calories and protein for one day.

    Gym days get more and rest days less, keeping the weekly total. `work` (optional) describes the
    day's activities: {"blocks": [(desk/standing/physical, hours), ...], "base_job": the profile's usual
    job} (or a single {"job", "hours"}). More active stretches add energy, and on hard days (anything
    physical, or 10+ busy hours) half the deficit is given back so you don't run on empty.
    Returns (kcal, protein_g).
    """
    kcal, protein = targets.kcal, targets.protein_g
    if gym_days_per_week not in (0, 7):
        if gym:
            kcal, protein = kcal + GYM_DAY_EXTRA_KCAL, protein + GYM_DAY_EXTRA_PROTEIN
        else:
            rest_days = 7 - gym_days_per_week
            kcal = round(kcal - GYM_DAY_EXTRA_KCAL * gym_days_per_week / rest_days)
    parts = work_blocks(work)
    if parts:
        base = work.get("base_job")
        kcal += sum(work_extra(targets.bmr, base, j, h) for j, h in parts)
        if is_hard(work):
            kcal += max(0, targets.tdee - targets.kcal) // 2
            protein += HARD_DAY_PROTEIN
    return max(CALORIE_FLOOR[sex], round(kcal)), protein


def kg_to_lb(kg):
    return kg * 2.20462


def lb_to_kg(lb):
    return lb / 2.20462


def cm_to_in(cm):
    return cm / 2.54


def in_to_cm(inches):
    return inches * 2.54
