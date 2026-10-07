import pytest

from mealplanner.nutrition import (
    CALORIE_FLOOR, MAX_PACE_KG_WEEK, bmr_mifflin, clamp_pace, compute_targets,
    day_targets, kg_to_lb, lb_to_kg, macro_split, tdee,
)


def test_bmr_male():
    # 10*85 + 6.25*190 - 5*25 + 5
    assert bmr_mifflin(85, 190, 25, "male") == pytest.approx(1917.5)


def test_bmr_female():
    # 10*60 + 6.25*165 - 5*30 - 161
    assert bmr_mifflin(60, 165, 30, "female") == pytest.approx(1320.25)


def test_bmr_rejects_unknown_sex():
    with pytest.raises(ValueError):
        bmr_mifflin(80, 180, 30, None)


def test_tdee_uses_activity_multiplier():
    assert tdee(2000, "sedentary") == pytest.approx(2400)
    assert tdee(2000, "moderate") == pytest.approx(3100)


def test_pace_is_capped():
    assert clamp_pace(1.5, 85, 78) == MAX_PACE_KG_WEEK
    assert clamp_pace(0.5, 85, 78) == 0.5
    assert clamp_pace(-1, 85, 78) == 0


def test_pace_is_zero_at_goal():
    assert clamp_pace(0.5, 78, 78) == 0
    assert clamp_pace(0.5, 75, 78) == 0


def test_default_profile_targets():
    t = compute_targets(85, 190, 25, "male", "light", 0.5, 78)
    # TDEE = 1917.5 * 1.375 = 2636.6; deficit = 0.5*7700/7 = 550
    assert t.tdee == 2637
    assert t.kcal == 2090
    assert t.protein_g == 153  # 1.8 * 85
    assert t.pace_effective == pytest.approx(0.5, abs=0.01)
    assert not t.floor_applied
    assert not t.pace_capped
    assert t.weeks_to_goal == pytest.approx(14.0, abs=0.2)


def test_excessive_pace_is_capped_in_targets():
    t = compute_targets(85, 190, 25, "male", "light", 2.0, 78)
    assert t.pace_capped
    assert t.pace_effective <= MAX_PACE_KG_WEEK + 0.01


def test_calorie_floor_applies():
    # small, sedentary, older woman asking for the max pace
    t = compute_targets(50, 150, 70, "female", "sedentary", 0.75, 45)
    assert t.kcal == CALORIE_FLOOR["female"]
    assert t.floor_applied
    assert t.pace_effective < 0.75


def test_maintenance_when_at_goal():
    t = compute_targets(78, 190, 25, "male", "light", 0.5, 78)
    assert t.kcal == round(t.tdee / 10) * 10
    assert t.weeks_to_goal is None


def test_macros_add_up():
    t = compute_targets(85, 190, 25, "male", "light", 0.5, 78)
    total = t.protein_g * 4 + t.carbs_g * 4 + t.fat_g * 9
    assert total == pytest.approx(t.kcal, abs=15)


def test_macro_split_never_negative_carbs():
    fat, carbs = macro_split(1200, 300, 100)
    assert carbs == 0
    assert fat >= 60


def test_gym_days_keep_weekly_total():
    t = compute_targets(85, 190, 25, "male", "light", 0.5, 78)
    gym_kcal, gym_p = day_targets(t, True, 3, "male")
    rest_kcal, rest_p = day_targets(t, False, 3, "male")
    assert gym_kcal > t.kcal > rest_kcal
    assert gym_p > rest_p
    assert 3 * gym_kcal + 4 * rest_kcal == pytest.approx(7 * t.kcal, abs=5)


def test_unit_conversion_round_trip():
    assert lb_to_kg(kg_to_lb(85)) == pytest.approx(85)


def test_hard_workdays_get_more_food():
    t = compute_targets(85, 190, 25, "male", 1.305, 0.5, 78)
    rest, _ = day_targets(t, False, 0, "male")
    desk, _ = day_targets(t, False, 0, "male", work={"job": "desk", "hours": 8, "base_job": "desk"})
    feet, _ = day_targets(t, False, 0, "male", work={"job": "standing", "hours": 8, "base_job": "desk"})
    phys, p_phys = day_targets(t, False, 0, "male", work={"job": "physical", "hours": 8, "base_job": "desk"})
    long_desk, _ = day_targets(t, False, 0, "male", work={"job": "desk", "hours": 11, "base_job": "desk"})
    assert desk == rest < feet < phys
    # physical: 8 h at 2 METs over a desk (1917.5 / 24 per MET-hour) plus half the deficit given back
    assert phys - rest == pytest.approx(round(1917.5 / 24 * 8 * 2) + (t.tdee - t.kcal) // 2, abs=2)
    assert p_phys == t.protein_g + 10
    assert long_desk > rest      # a 11-hour day is a hard day even at a desk
