import pytest

from mealplanner.costing import (
    from_grams, macros_for, per_serving, price_per_100g, protein_per_100kcal, recipe_totals, to_grams,
)


def test_to_grams_units():
    assert to_grams(250, "g") == 250
    assert to_grams(200, "ml") == 200
    assert to_grams(6, "pcs", piece_g=60) == 360


def test_pieces_need_piece_weight():
    with pytest.raises(ValueError):
        to_grams(2, "pcs")


def test_from_grams_inverts_to_grams():
    assert from_grams(to_grams(3, "pcs", 45), "pcs", 45) == pytest.approx(3)


def test_price_per_100g():
    assert price_per_100g(398, 500) == pytest.approx(79.6)
    assert price_per_100g(None, 500) is None
    assert price_per_100g(100, 0) is None


def test_macros_for_weight():
    chicken = {"kcal": 105, "protein": 23.3, "carbs": 0, "fat": 1.9}
    m = macros_for(150, chicken)
    assert m["kcal"] == pytest.approx(157.5)
    assert m["protein"] == pytest.approx(34.95)


def test_recipe_totals_and_per_serving():
    ings = [
        {"name": "chicken", "grams": 200, "kcal": 105, "protein": 23.3, "carbs": 0, "fat": 1.9, "price_per_100g": 85},
        {"name": "rice", "grams": 300, "kcal": 156, "protein": 2.5, "carbs": 37.1, "fat": 0.3, "price_per_100g": 30},
        {"name": "salt", "grams": 2, "kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "price_per_100g": None},
    ]
    totals = recipe_totals(ings)
    assert totals["kcal"] == pytest.approx(210 + 468)
    assert totals["cost"] == pytest.approx(170 + 90)
    assert totals["unpriced"] == ["salt"]
    serving = per_serving(totals, 2)
    assert serving["kcal"] == pytest.approx(339)
    assert serving["cost"] == pytest.approx(130)


def test_per_serving_guards_zero():
    assert per_serving({"kcal": 100, "protein": 0, "carbs": 0, "fat": 0, "cost": 50}, 0)["kcal"] == 100


def test_protein_density():
    assert protein_per_100kcal(30, 300) == pytest.approx(10)
    assert protein_per_100kcal(5, 0) == 0
