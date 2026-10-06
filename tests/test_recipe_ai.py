import json

import pytest

from mealplanner import store
from mealplanner.db import execute, query
from mealplanner.llm import LLMError, extract_json, parse_events
from mealplanner.recipe_ai import validate

GOOD = {"name": "Chili chicken cabbage", "servings": 1, "active_min": 12, "total_min": 15,
        "meal_types": ["dinner"], "tags": ["spicy"], "cuisine": "korean", "spice_level": 2,
        "ingredients": [{"food": "Chicken breast", "grams": 150}, {"food": "cabbage", "grams": 100},
                        {"food": "Unicorn dust", "grams": 5}],
        "steps": ["Fry the chicken until cooked through.", "Add cabbage."],
        "kcal_per_serving": 99999}


class FakeModel:
    model = "fake"

    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_parse_events_joins_text():
    out = "\n".join([json.dumps({"type": "step_start"}),
                     json.dumps({"type": "text", "part": {"text": "{\"a\": "}}),
                     json.dumps({"type": "text", "part": {"text": "1}"}}), "garbage"])
    assert parse_events(out) == '{"a": 1}'


def test_extract_json_handles_fences_and_braces_in_strings():
    assert extract_json('Sure!\n```json\n{"name": "a {b}", "n": 1}\n```') == {"name": "a {b}", "n": 1}
    with pytest.raises(LLMError):
        extract_json("no json here")
    with pytest.raises(LLMError):
        extract_json('{"name": "cut')


def test_validate_recomputes_numbers_and_drops_unknown_foods(app):
    with app.app_context():
        recipe, problems, warnings = validate(GOOD, store.settings())
        assert not problems
        assert [i["name"] for i in recipe["ingredients"]] == ["Chicken breast", "Cabbage"]
        assert any("Unicorn dust" in w for w in warnings)
        # 150 g chicken (105/100 g) + 100 g cabbage (23/100 g), whatever the model claimed
        assert recipe["per_serving"]["kcal"] == pytest.approx(157.5 + 23)


def test_validate_blocks_allergens_and_dislikes(app):
    with app.app_context():
        execute("UPDATE settings SET allergies = 'egg', dislikes = 'cabbage' WHERE id = 1")
        data = dict(GOOD, ingredients=[{"food": "Egg", "grams": 120}, {"food": "Cabbage", "grams": 50}])
        _, problems, _ = validate(data, store.settings())
        assert any("allergy" in p for p in problems) and any("dislike" in p for p in problems)


def test_validate_rejects_junk(app):
    with app.app_context():
        assert validate("nope", store.settings())[1]
        _, problems, _ = validate({"name": "x", "ingredients": [], "steps": []}, store.settings())
        assert "no usable ingredients" in problems and "no steps" in problems


def test_generate_preview_and_save(app, client):
    fake = FakeModel("Here you go: " + json.dumps(GOOD))
    app.config["LLM_PROVIDER"] = fake
    page = client.post("/recipes/ai", data={"request": "spicy dinner"})
    assert page.status_code == 200 and b"Chili chicken cabbage" in page.data
    assert "spicy dinner" in fake.prompts[0] and "Chicken breast" in fake.prompts[0]
    resp = client.post("/recipes/ai/save", data={"raw": json.dumps(GOOD)}, follow_redirects=True)
    assert b"Saved" in resp.data
    with app.app_context():
        r = query("SELECT * FROM recipes WHERE name = 'Chili chicken cabbage'", one=True)
        assert r and r["meal_types"] == "dinner"


def test_save_rechecks_tampered_payload(app, client):
    with app.app_context():
        execute("UPDATE settings SET allergies = 'egg' WHERE id = 1")
    bad = dict(GOOD, ingredients=[{"food": "Egg", "grams": 120}])
    resp = client.post("/recipes/ai/save", data={"raw": json.dumps(bad)}, follow_redirects=True)
    assert b"can&#39;t be saved" in resp.data or b"can't be saved" in resp.data


def test_model_error_is_shown(app, client):
    app.config["LLM_PROVIDER"] = FakeModel(LLMError("timeout"))
    resp = client.post("/recipes/ai", data={"request": "x"}, follow_redirects=True)
    assert b"Couldn" in resp.data and b"timeout" in resp.data


def test_ai_page_without_model(client):
    assert b"No recipe model" in client.get("/recipes/ai").data


def test_event_error_explains_subscription_problem():
    from mealplanner.llm import event_error
    out = json.dumps({"type": "error", "error": {"name": "APIError", "data": {
        "message": "Upstream request failed: An active OpenCode Go subscription is required to use Go models."}}})
    assert "subscription" in event_error(out)
    assert event_error('{"type": "text"}') is None
