from datetime import date, timedelta

import pytest

from mealplanner.price_model import fit, trend, weight

T = date(2026, 10, 7)
FOODS = {1: {"base": 100.0, "category": "poultry"}, 2: {"base": 200.0, "category": "poultry"},
         3: {"base": 50.0, "category": "veg"}, 4: {"base": None, "category": "sauce"}}


def iso(days_ago):
    return (T - timedelta(days=days_ago)).isoformat()


def test_no_data_uses_the_settings_prior():
    m = fit(FOODS, [], 0.9, T)
    assert m["global"] == pytest.approx(0.9)
    assert m["foods"][1]["price"] == pytest.approx(90) and m["foods"][1]["source"] == "estimate"
    assert m["foods"][4]["price"] is None


def test_more_receipts_mean_more_trust():
    one = fit(FOODS, [(1, 80, iso(0))], 1.0, T)["foods"][1]["price"]
    three = fit(FOODS, [(1, 80, iso(0)), (1, 80, iso(1)), (1, 80, iso(2))], 1.0, T)["foods"][1]["price"]
    assert 80 < three < one < 100


def test_category_and_overall_level_carry_over():
    m = fit(FOODS, [(1, 70, iso(0)), (1, 70, iso(3))], 1.0, T)
    # chicken thigh was never bought but shares chicken breast's category
    assert m["foods"][2]["price"] < 200 and m["foods"][2]["source"] == "category"
    # veg moves a little with the overall level, less than poultry
    assert m["foods"][2]["price"] / 200 < m["foods"][3]["price"] / 50 < 1


def test_old_receipts_count_less():
    assert weight(iso(60), T) == pytest.approx(0.5)
    recent = fit(FOODS, [(1, 120, iso(200)), (1, 80, iso(0))], 1.0, T)["foods"][1]["price"]
    assert recent < 100


def test_trend_detects_rising_prices():
    obs = [(0.0, 1.0, iso(90 - i * 30), 100 * 1.05 ** i) for i in range(4)]
    assert trend(obs) == pytest.approx(0.05, abs=0.01)
    assert trend(obs[:2]) is None


def test_bad_prices_ignored():
    m = fit(FOODS, [(1, 0, iso(0)), (99, 50, iso(0)), (4, 30, iso(0))], 1.0, T)
    assert m["observations"] == 0
