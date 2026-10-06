import json

import pytest

from mealplanner import llm, store
from mealplanner.db import execute, query
from mealplanner.pricing import currency, factor


def test_factor_by_area_and_shop():
    assert factor({"country": "JP", "area": "city", "shop": "supermarket"}) == 1.0
    assert factor({"country": "JP", "area": "tokyo", "shop": "gyomu"}) == pytest.approx(1.08 * 0.82)
    assert factor({"country": "US", "shop": "supermarket"}) == pytest.approx(0.0067 * 1.45)
    assert currency({"country": "GB"}) == "£" and currency({}) == "¥"


def test_reference_prices_follow_shop_but_paid_prices_win(app, client):
    with app.app_context():
        base = store.food_by_name("Chicken breast")["current_price"]
        execute("UPDATE settings SET shop = 'gyomu' WHERE id = 1")
        cheaper = store.food_by_name("Chicken breast")
        assert cheaper["current_price"] == pytest.approx(base * 0.82) and cheaper["estimated"]
    client.post("/pantry/new", data={"name": "Chicken breast", "quantity": "500", "unit": "g", "price_paid": "500",
                                     "location": "fridge", "kcal": "105", "protein": "23.3", "carbs": "0", "fat": "1.9"})
    with app.app_context():
        paid = store.food_by_name("Chicken breast")
        # paid 100/100 g against a gyomu-adjusted 69.7: the estimate moves well past halfway toward 100
        assert 85 < paid["current_price"] < 100 and not paid["estimated"]


def test_currency_shows_in_pages(app, client):
    with app.app_context():
        execute("UPDATE settings SET country = 'GB' WHERE id = 1")
    page = client.get("/recipes/").data.decode()
    assert "£" in page and "¥" not in page


def settings_form(**kw):
    from tests.test_settings_view import form
    data = form()
    data.update(kw)
    return data


def test_gemini_key_saved_kept_and_cleared(app, client):
    client.post("/settings/", data=settings_form(gemini_key="AIza-test-key"))
    with app.app_context():
        assert store.settings()["gemini_key"] == "AIza-test-key"
    page = client.get("/settings/").data.decode()
    assert "AIza-test-key" not in page and "saved" in page
    client.post("/settings/", data=settings_form(gemini_key=""))
    with app.app_context():
        assert store.settings()["gemini_key"] == "AIza-test-key"
    client.post("/settings/", data=settings_form(gemini_key="-"))
    with app.app_context():
        assert store.settings()["gemini_key"] == ""


def test_provider_prefers_gemini_when_key_set(app, monkeypatch):
    monkeypatch.setenv("MEALPLANNER_LLM", "auto")
    with app.app_context():
        execute("UPDATE settings SET gemini_key = 'k' WHERE id = 1")
        p = llm.provider()
        assert isinstance(p, llm.GeminiProvider) and p.key == "k"


def test_gemini_request_shape(tmp_path, monkeypatch):
    sent = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}).encode()

    def fake_urlopen(req, timeout=None):
        sent["url"] = req.full_url
        sent["headers"] = dict(req.header_items())
        sent["body"] = json.loads(req.data)
        return Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    img = tmp_path / "r.jpg"
    img.write_bytes(b"\xff\xd8jpeg")
    out = llm.GeminiProvider("secret").complete("read this", images=[str(img)], model="opencode-go/vision")
    assert out == '{"ok": true}'
    assert "gemini-3.8-flash:generateContent" in sent["url"] and "secret" not in sent["url"]
    assert sent["headers"]["X-goog-api-key"] == "secret"
    parts = sent["body"]["contents"][0]["parts"]
    assert parts[0]["text"] == "read this" and parts[1]["inline_data"]["mime_type"] == "image/jpeg"
