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
                   {"name_ja": "レジ袋", "name_en": "Plastic bag", "kind": "other", "food": None, "grams": 0,
                    "price_yen": 68}]}


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
    assert not unknown["include"] and any("レジ袋" in w for w in warnings)
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
    assert "Found 4 items" in page and "Looks right: add 3" in page and "not food" in page
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


def test_unknown_food_is_created_from_the_receipt(app, client):
    resp = client.post("/receipts/save", data={"count": "1", "include_0": "on", "food_0": "Dragon fruit",
                                               "kind_0": "cooking", "grams_0": "300", "price_0": "300",
                                               "new_0": json.dumps({"kcal": 50, "protein": 1.1, "carbs": 11,
                                                                    "fat": 0.4, "category": "fruit"})},
                       follow_redirects=True)
    assert b"New foods: Dragon fruit" in resp.data
    with app.app_context():
        f = store.food_by_name("Dragon fruit")
        assert f["kcal"] == 50 and f["category"] == "fruit" and f["price_per_100g"] == 100
        assert query("SELECT quantity FROM pantry_items WHERE food_id = ?", (f["id"],), one=True)["quantity"] == 300


def test_snack_from_receipt_goes_to_stash_and_eating_logs_it(app, client):
    snack = {"name_ja": "ポテトチップス うすしお", "name_en": "Potato chips (lightly salted)", "kind": "snack",
             "food": None, "grams": 120, "packs": 2, "price_yen": 276,
             "new_food": {"kcal": 554, "protein": 4.7, "carbs": 54.7, "fat": 35.2, "category": "snack"}}
    with app.app_context():
        rows, _, _ = receipts.rows_from_reply({"items": [snack]}, TODAY)
    r = rows[0]
    assert r["include"] and r["food"] == "Potato chips (lightly salted)" and r["new"]["category"] == "snack"
    resp = client.post("/receipts/save", data={"count": "1", "include_0": "on", "food_0": r["food"], "kind_0": "snack",
                                               "packs_0": "2", "grams_0": "120", "price_0": "276",
                                               "location_0": "shelf", "new_0": json.dumps(r["new"])})
    assert resp.headers["Location"].endswith("/pantry/snacks")
    page = client.get("/pantry/snacks").data.decode()
    assert "Potato chips (lightly salted)" in page and "332 kcal a pack" in page
    with app.app_context():
        item = query("SELECT id FROM pantry_items", one=True)["id"]
    client.post(f"/pantry/snacks/{item}/eat", data={"share": "1"})
    client.post(f"/pantry/snacks/{item}/eat", data={"share": "0.5"})
    with app.app_context():
        logged = query("SELECT * FROM food_log WHERE source = 'snack' ORDER BY id")
        assert [e["kcal"] for e in logged] == [332, 166] and logged[0]["yen"] == 0
        assert query("SELECT quantity FROM pantry_items WHERE id = ?", (item,), one=True)["quantity"] == 30
    page = client.get("/pantry/snacks").data.decode()
    assert '<span class="num-big">2</span>' in page


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


def test_last_scan_kept_when_phone_drops(app, client):
    app.config["LLM_PROVIDER"] = FakeVision()
    client.post("/receipts/", data={"photo": (io.BytesIO(b"\xff\xd8fakejpeg"), "r.jpg")},
                content_type="multipart/form-data")
    page = client.get("/receipts/").data.decode()
    assert "Your last receipt is ready" in page and "4 items" in page
    assert "Found 4 items" in client.get("/receipts/last").data.decode()
    client.post("/receipts/save", data={"count": "0"})
    assert "Your last receipt is ready" not in client.get("/receipts/").data.decode()
    assert client.get("/receipts/last").status_code == 302


def test_cooking_items_replan_week_and_leave_the_list(app, client):
    from mealplanner import plans
    from mealplanner.db import execute
    with app.app_context():
        execute("UPDATE settings SET age = 25, sex = 'male', setup_done = 1 WHERE id = 1")
        first = plans.current_week()[0]
        plans.generate_week(first)
        before = {i["name"]: i["grams"] for i in plans.shopping_preview(first)}
    # buy plenty of the biggest thing on the list
    name = max(before, key=before.get)
    resp = client.post("/receipts/save", data={"count": "1", "include_0": "on", "food_0": name,
                                               "kind_0": "cooking", "grams_0": str(int(before[name]) + 500),
                                               "price_0": "2400", "location_0": "fridge", "expiry_0": "2026-10-14"},
                       follow_redirects=True)
    assert b"now use what you bought" in resp.data
    with app.app_context():
        after = {i["name"]: i["grams"] for i in plans.shopping_preview(first)}
    assert after.get(name, 0) < before[name]
