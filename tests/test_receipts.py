import io
import json
from datetime import date

from mealplanner import receipts, store
from mealplanner.db import query

TODAY = date(2026, 10, 7)
REPLY = {"store": "Life", "date": "2026-10-06", "total_yen": 932,
         "items": [{"name_ja": "鶏むね肉", "food": "Chicken breast", "grams": 520, "price_yen": 398},
                   {"name_ja": "卵 10個入", "food": "Egg", "grams": 600, "price_yen": 268},
                   {"name_ja": "冷凍ほうれん草", "food": "Frozen spinach", "grams": 300, "price_yen": 198},
                   {"name_ja": "謎の商品", "food": None, "grams": 0, "price_yen": 68}]}


class FakeVision:
    model = "fake"

    def __init__(self):
        self.calls = []

    def complete(self, prompt, images=(), model=None):
        self.calls.append((prompt, list(images), model))
        return "```json\n" + json.dumps(REPLY, ensure_ascii=False) + "\n```"


def test_rows_from_reply(app):
    with app.app_context():
        rows, header, warnings = receipts.rows_from_reply(REPLY, TODAY)
    assert header == {"store": "Life", "date": "2026-10-06", "total": 932}
    chicken, egg, spinach, unknown = rows
    assert chicken["food"] == "Chicken breast" and chicken["expiry"] == "2026-10-09" and chicken["include"]
    assert egg["expiry"] == "2026-10-21"
    assert spinach["location"] == "freezer"
    assert not unknown["include"] and any("謎の商品" in w for w in warnings)
    assert not any("total says" in w for w in warnings)


def test_total_mismatch_warns(app):
    with app.app_context():
        _, _, warnings = receipts.rows_from_reply(dict(REPLY, total_yen=3000), TODAY)
    assert any("total says" in w for w in warnings)


def test_upload_review_and_save(app, client):
    fake = FakeVision()
    app.config["LLM_PROVIDER"] = fake
    resp = client.post("/receipts/", data={"photo": (io.BytesIO(b"\xff\xd8fakejpeg"), "r.jpg")},
                       content_type="multipart/form-data")
    assert resp.status_code == 200 and "鶏むね肉" in resp.data.decode()
    page = resp.data.decode()
    assert "Found 4 items" in page and "Looks right: add" in page and "Not matched to a food" in page
    assert 'data-scan="receipt"' in client.get("/receipts/").data.decode()
    prompt, images, model = fake.calls[0]
    assert len(images) == 1 and "vision" in model and "Chicken breast" in prompt

    form = {"count": "2", "include_0": "on", "food_0": "Chicken breast", "grams_0": "520", "price_0": "398",
            "expiry_0": "2026-10-09", "location_0": "fridge",
            "food_1": "Egg", "grams_1": "600", "price_1": "268", "expiry_1": "2026-10-21", "location_1": "fridge"}
    client.post("/receipts/save", data=form)
    with app.app_context():
        items = query("SELECT * FROM pantry_items")
        assert len(items) == 1 and items[0]["price_paid"] == 398 and items[0]["quantity"] == 520
        assert 76.5 < store.food_by_name("Chicken breast")["current_price"] < 80


def test_save_rejects_unknown_food(app, client):
    resp = client.post("/receipts/save", data={"count": "1", "include_0": "on", "food_0": "Dragon fruit",
                                               "grams_0": "100", "price_0": "300"}, follow_redirects=True)
    assert b"isn&#39;t in your food list" in resp.data or b"isn't in your food list" in resp.data


def test_non_image_rejected(app, client):
    app.config["LLM_PROVIDER"] = FakeVision()
    resp = client.post("/receipts/", data={"photo": (io.BytesIO(b"x"), "notes.txt")},
                       content_type="multipart/form-data", follow_redirects=True)
    assert b"isn&#39;t a photo" in resp.data or b"isn't a photo" in resp.data


def test_api_for_other_ocr_apps(app, client):
    class FakeMatcher:
        model = "fake"

        def complete(self, prompt, images=(), model=None):
            return json.dumps({"items": [{"name_ja": "木綿豆腐", "food": "Firm tofu", "grams": 450}]})
    app.config["LLM_PROVIDER"] = FakeMatcher()
    resp = client.post("/receipts/api", json={"store": "Aeon", "date": "2026-10-06",
                                              "items": [{"name_ja": "木綿豆腐", "price_yen": 108}]})
    data = resp.get_json()
    assert data["rows"][0]["food"] == "Firm tofu" and data["rows"][0]["grams"] == 450
    assert client.post("/receipts/api", json={"nope": 1}).status_code == 400
