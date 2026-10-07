import json

import pytest

from mealplanner import ai_budget, llm, store
from mealplanner.db import execute, query


class Fake:
    model = "fake"

    def __init__(self, reply):
        self.reply, self.calls = reply, 0

    def complete(self, prompt, images=(), model=None):
        self.calls += 1
        return self.reply


ASK = {"answer": "Try these.", "ideas": [
    {"kind": "dish", "name": "Jollof chicken rice", "what": "Tomato pepper rice with chicken", "why": "Big flavour", "kcal": 550},
    {"kind": "spice", "name": "Berbere", "what": "Ethiopian chili blend", "why": "Warm heat", "kcal": 5},
    {"kind": "nonsense", "name": "", "what": "dropped"}]}


def test_saver_caches_and_limits(app, monkeypatch):
    fake = Fake('{"ok": 1}')
    app.config.update(LLM_PROVIDER=fake, AI_SAVER=True)
    with app.test_request_context():
        p = llm.provider()
        assert p.complete("same question") == p.complete("same question")
        assert fake.calls == 1                                  # second one came from the cache
        ai_budget.fresh(p).complete("same question")
        assert fake.calls == 2                                  # "another one" skips the cache
        monkeypatch.setattr(ai_budget, "PER_PERSON_PER_DAY", 2)
        with pytest.raises(llm.LLMError, match="resets tomorrow"):
            p.complete("a brand new question")
        assert ai_budget.used_today()[0] == 2


def test_ask_page(profile, client):
    profile.config.update(LLM_PROVIDER=Fake(json.dumps(ASK)))
    assert b"Ask Zettai" in client.get("/recipes/ask").data
    page = client.post("/recipes/ask", data={"q": "something west african"}).data.decode()
    assert "Jollof chicken rice" in page and "Make it a recipe" in page and "Save to my sauces" in page
    client.post("/recipes/ask/keep", data={"name": "Berbere", "what": "Ethiopian chili blend", "kcal": "5"})
    with profile.app_context():
        assert query("SELECT name FROM my_condiments", one=True)["name"] == "Berbere"


def test_cuisine_ratings_and_custom(profile, client):
    client.post("/taste/cuisines", data={"cuisine_korean": "love", "cuisine_italian": "like",
                                         "cuisine_british": "no", "new_cuisine": "Georgian"})
    with profile.app_context():
        s = store.settings()
        assert s["cuisines_loved"] == "korean" and s["cuisines_liked"].split(",") == ["italian", "georgian"]
        assert s["cuisines_tired"] == "british" and s["cuisines_custom"] == "georgian"
    page = client.get("/taste/").data.decode()
    assert "Georgian" in page and "Soul Food" in page


def test_loved_cuisine_scores_higher():
    from mealplanner.taste import recipe_score
    r = {"tag_list": [], "cuisine": "korean", "servings": 1, "ingredients": []}
    loved = recipe_score(r, {"cuisines_loved": ["korean"]})
    liked = recipe_score(r, {"cuisines_liked": ["korean"]})
    plain = recipe_score(r, {})
    assert loved > liked > plain


def test_idea_with_cuisine(profile, client):
    fake = Fake(json.dumps({"name": "Kimchi tofu stew", "servings": 1, "ingredients": [{"food": "Firm tofu", "grams": 150}],
                            "steps": ["Simmer."]}))
    fake.prompts = []
    orig = fake.complete
    def remember(prompt, images=(), model=None):
        fake.prompts.append(prompt)
        return orig(prompt)
    fake.complete = remember
    profile.config.update(LLM_PROVIDER=fake)
    page = client.get("/recipes/ai").data.decode()
    assert "Surprise me" in page and "Soul Food" in page
    client.post("/recipes/ai", data={"request": "quick", "cuisine": "korean"})
    assert "A korean dish." in fake.prompts[-1]
