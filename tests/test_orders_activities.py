import io
import json
from datetime import date

from mealplanner import llm, orders, plans
from mealplanner.db import execute, query
from mealplanner.nutrition import activity_burn, work_extra

WED = date(2026, 10, 7)
REPLY = {"place": "McDonald's", "total": 1480, "items": [
    {"name": "Big Mac", "qty": 1, "kcal": 525, "protein": 26, "carbs": 41, "fat": 28, "price": 480, "confidence": "high"},
    {"name": "Large fries", "qty": 2, "kcal": 1000, "protein": 12, "carbs": 120, "fat": 50, "price": 760},
    {"name": "Delivery fee", "qty": 1, "kcal": 0, "price": 240},
    {"name": "Mystery sauce", "qty": 1, "kcal": 0, "price": 0},
]}


class FakeAI:
    name = "fake"

    def __init__(self):
        self.calls = []

    def complete(self, prompt, images=(), model=None):
        self.calls.append((prompt, list(images)))
        return json.dumps(REPLY)


def test_order_rows_skip_fees_and_check_numbers():
    rows, header, warnings = orders.rows_from_reply(REPLY)
    assert [r["name"] for r in rows] == ["Big Mac", "Large fries ×2", "Mystery sauce"]
    assert rows[0]["include"] and not rows[2]["include"]          # no calorie guess: left unticked
    assert rows[1]["confidence"] == "low"                         # missing confidence counts as low
    assert header == {"place": "McDonald's", "total": 1480}
    assert any("no calorie guess" in w for w in warnings)
    silly = orders.rows_from_reply({"items": [{"name": "Salad", "kcal": 100, "protein": 90, "fat": 40}]})[0]
    assert silly[0]["protein"] == 0 and silly[0]["kcal"] == 100   # macros way past the calories are dropped


def test_order_entries_scale_to_your_share():
    form = {"count": "2", "share": "0.5", "include_0": "on", "name_0": "Pizza", "kcal_0": "1600", "protein_0": "60",
            "price_0": "2000", "name_1": "Cola", "kcal_1": "200"}
    entries, errors = orders.entries_from_form(form)
    assert entries == [{"name": "Pizza (50%)", "kcal": 800, "protein": 30.0, "carbs": 0.0, "fat": 0.0, "yen": 1000}]
    entries, _ = orders.entries_from_form({**form, "paid_all": "on"})
    assert entries[0]["yen"] == 2000
    _, errors = orders.entries_from_form({"count": "1", "include_0": "on", "name_0": "Soup", "kcal_0": ""})
    assert errors


def test_order_photo_to_food_log(profile, client, monkeypatch):
    ai = FakeAI()
    monkeypatch.setattr(llm, "provider", lambda: ai)
    page = client.get("/log/?tab=order").data.decode()
    assert "Ordered food" in page and "Estimate calories" in page
    resp = client.post("/log/order", data={"photo": (io.BytesIO(b"\x89PNG fake"), "order.png")},
                       content_type="multipart/form-data")
    html = resp.data.decode()
    assert "Check your order" in html and "Big Mac" in html and "Delivery fee" not in html
    assert ai.calls[0][1]                                          # the photo went to the model
    resp = client.post("/log/order/save", data={"count": "2", "share": "1", "slot": "dinner", "paid_all": "on",
                                                "include_0": "on", "name_0": "Big Mac", "kcal_0": "525",
                                                "protein_0": "26", "price_0": "480",
                                                "include_1": "on", "name_1": "Large fries ×2", "kcal_1": "1000",
                                                "price_1": "760"}, follow_redirects=True)
    assert b"Logged 2 items from your order, 1525 kcal" in resp.data
    with profile.app_context():
        rows = query("SELECT * FROM food_log WHERE source = 'order' ORDER BY id")
        assert [(r["name"], r["kcal"], r["yen"], r["slot"]) for r in rows] == [
            ("Big Mac", 525, 480, "dinner"), ("Large fries ×2", 1000, 760, "dinner")]


def test_order_text_paste(profile, client, monkeypatch):
    ai = FakeAI()
    monkeypatch.setattr(llm, "provider", lambda: ai)
    client.post("/log/order", data={"text": "Big Mac x1 480 yen"})
    assert "Big Mac x1 480 yen" in ai.calls[0][0] and not ai.calls[0][1]


def test_order_needs_ai(profile, client):
    resp = client.post("/log/order", data={"text": "pizza"}, follow_redirects=True)
    assert b"Gemini key" in resp.data


def test_activity_burn_estimates():
    assert activity_burn(1800, "desk", 8) == 300
    assert activity_burn(1800, "physical", 8) > activity_burn(1800, "standing", 8) > activity_burn(1800, "desk", 8)
    assert activity_burn(1800, "physical", 1.5, "gym") == 450
    assert activity_burn(0, "physical", 8) == 0
    # a shift on your feet adds the difference from your usual desk day
    assert work_extra(1800, "desk", "standing", 8) == 600
    assert work_extra(1800, "standing", "standing", 8) == 0


def test_saved_activities_come_back_once_each(profile, client):
    client.post("/plan/generate")
    for day in ("2026-10-08", "2026-10-09"):
        client.post(f"/plan/day/{day}/activity", data={"kind": "parttime", "label": "Konbini shift",
                                                        "start": "17:00", "end": "22:00", "intensity": "standing"})
    client.post("/plan/day/2026-10-09/activity", data={"kind": "school", "label": "Calculus",
                                                       "start": "09:00", "end": "12:00"})
    with profile.app_context():
        saved = plans.saved_activities()
    assert [a["label"] for a in saved] == ["Calculus", "Konbini shift"]
    page = client.get("/plan/").data.decode()
    assert "Add one you have" in page and "data-act-fill" in page
    assert "~" in page and "kcal</span>" in page                  # burn estimate next to each activity


def test_home_target_counts_work_before_planning(profile, client):
    """Today's target moves with a physical shift even when the week isn't planned yet."""
    with profile.app_context():
        execute("UPDATE schedule_days SET work_start = NULL, work_end = NULL")
        execute("DELETE FROM plan_days")
    before = client.get("/").data.decode()
    client.post(f"/plan/day/{WED.isoformat()}/activity", data={"kind": "work", "label": "Moving job",
                                                               "start": "08:00", "end": "17:00",
                                                               "intensity": "physical"})
    with profile.app_context():
        execute("DELETE FROM plan_days")
    from mealplanner.views.main import today_targets
    from mealplanner import store
    with profile.test_request_context():
        from flask import session
        session["profile"] = "main"
        s = store.settings()
        kcal, _ = today_targets(s, store.targets(s), WED)
        base = store.targets(s).kcal
    assert kcal > base + 500
    assert before
