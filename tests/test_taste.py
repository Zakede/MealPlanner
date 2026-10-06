from datetime import date

import pytest

from mealplanner import plans, store
from mealplanner.db import query
from mealplanner.taste import bayes_stars, insights, is_favorite, recipe_score, tag_affinity

RECIPE = {"id": 1, "tag_list": ["spicy", "crunchy"], "cuisine": "korean", "servings": 1, "active_min": 10,
          "ingredients": [{"id": 10, "grams": 100}, {"id": 11, "grams": 50}]}


def test_bayes_pulls_single_rating_toward_prior():
    assert bayes_stars([]) == pytest.approx(3.5)
    assert bayes_stars([5]) == pytest.approx((5 + 7) / 3)
    assert not is_favorite([5])
    assert is_favorite([5, 5])


def test_score_rises_with_good_ratings():
    base = recipe_score(RECIPE, {})
    assert recipe_score(RECIPE, {"stars": [5, 5, 4]}) > base
    assert recipe_score(RECIPE, {"stars": [1, 2]}) < base


def test_preferences_shift_score():
    base = recipe_score(RECIPE, {})
    assert recipe_score(RECIPE, {"flavor_likes": ["spicy"]}) > base
    assert recipe_score(RECIPE, {"cuisines_tired": ["korean"]}) < base
    assert recipe_score(RECIPE, {"ingredient_scores": {10: "dislike"}}) < base
    assert recipe_score(RECIPE, {"ingredient_scores": {10: "small"}}) < base   # 100 g is more than "a bit"
    assert recipe_score(RECIPE, {"ingredient_scores": {11: "small"}}) > base - 0.11
    assert recipe_score(RECIPE, {"feedback_tags": ["too spicy"]}) < base


def test_score_stays_in_range():
    assert 0 <= recipe_score(RECIPE, {"stars": [1] * 10, "ingredient_scores": {10: "dislike", 11: "dislike"}}) <= 1
    assert recipe_score(RECIPE, {"stars": [5] * 10, "flavor_likes": ["spicy", "crunchy"],
                                 "cuisines_liked": ["korean"]}) <= 1


def test_tag_affinity_learns_from_stars():
    aff = tag_affinity([(1, 5), (1, 5), (2, 1)], {1: ["crunchy"], 2: ["sweet"]})
    assert aff["crunchy"] > 0 > aff["sweet"]


def test_insights_suggest_lower_spice():
    recipes = {1: {"spice_level": 3}, 2: {"spice_level": 4}}
    hints = insights([{"recipe_id": 1, "tags": "too spicy"}, {"recipe_id": 2, "tags": "too spicy,too salty"}],
                     recipes, 4)
    assert any("spice tolerance 2" in h for h in hints)


def test_rating_saves_and_changes_planner_taste(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        meal = next(m for m in plans.meals_between(date(2026, 10, 7), date(2026, 10, 7)) if m["recipe_id"])
        before = plans.taste_context(store.recipes(), store.settings())[0][meal["recipe_id"]]
    page = client.post(f"/cook/{meal['id']}/done", follow_redirects=True)
    assert b"How was it?" in page.data
    client.post(f"/cook/{meal['id']}/rate", data={"stars": "5", "tag_loved it": "on"})
    with profile.app_context():
        r = query("SELECT * FROM ratings", one=True)
        assert r["stars"] == 5 and r["tags"] == "loved it"
        after = plans.taste_context(store.recipes(), store.settings())[0][meal["recipe_id"]]
        assert after > before


def test_rating_needs_stars(profile, client):
    client.post("/plan/generate")
    with profile.app_context():
        meal = next(m for m in plans.meals_between(date(2026, 10, 7), date(2026, 10, 7)) if m["recipe_id"])
    resp = client.post(f"/cook/{meal['id']}/rate", data={}, follow_redirects=True)
    assert b"Pick 1 to 5 stars" in resp.data


def test_ingredient_scores_saved(app, client):
    with app.app_context():
        natto = store.food_by_name("Natto")["id"]
    client.post("/taste/", data={f"f{natto}": "dislike"})
    with app.app_context():
        assert query("SELECT score FROM taste_scores WHERE food_id = ?", (natto,), one=True)["score"] == "dislike"
    assert client.get("/taste/").status_code == 200
