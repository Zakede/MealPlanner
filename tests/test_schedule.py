from mealplanner.db import query
from mealplanner.schedule import busy, hhmm, minutes, slot_limits

WORKDAY = {"wake": "07:00", "work_start": "09:00", "work_end": "18:00", "commute_min": 40, "gym": 1,
           "breakfast_time": "07:30", "lunch_time": "12:30", "dinner_time": "19:00", "effort": "low", "away": 0}
FREE = dict(WORKDAY, work_start=None, work_end=None, commute_min=0, effort="full")


def test_time_helpers():
    assert minutes("07:30") == 450
    assert hhmm(450) == "07:30"
    assert hhmm(-15) == "23:45"


def test_workday_limits():
    lim = slot_limits(WORKDAY)
    assert lim["breakfast"]["max_total"] == 30   # leave 08:20, wake 07:00: 70 min, capped at 30
    assert lim["lunch"]["away"] and lim["lunch"]["max_total"] == 0
    assert lim["dinner"]["max_total"] == 20      # home 18:40, dinner 19:00
    assert lim["dinner"]["max_active"] == 15
    assert busy(WORKDAY)


def test_free_day_allows_big_cook():
    lim = slot_limits(FREE)
    assert lim["dinner"]["max_total"] == 120 and lim["dinner"]["max_active"] == 120
    assert not lim["lunch"]["away"]
    assert not busy(FREE)


def test_away_day_blocks_cooking():
    lim = slot_limits(dict(FREE, away=1))
    assert lim["lunch"]["away"] and lim["dinner"]["away"]


def schedule_form():
    data = {}
    for wd in range(7):
        for k, v in WORKDAY.items():
            if k not in ("gym", "away"):
                data[f"d{wd}_{k}"] = v
    return data


def test_save_schedule(app, client):
    data = schedule_form()
    data["d6_effort"] = "full"
    data["d6_away"] = "on"
    resp = client.post("/schedule/", data=data, follow_redirects=True)
    assert b"Schedule saved" in resp.data
    with app.app_context():
        sun = query("SELECT * FROM schedule_days WHERE weekday = 6", one=True)
        assert sun["away"] == 1 and sun["effort"] == "full" and sun["gym"] == 0


def test_bad_time_rejected(client):
    data = schedule_form()
    data["d0_wake"] = "25:00"
    resp = client.post("/schedule/", data=data, follow_redirects=True)
    assert b"must look like" in resp.data


def test_half_work_hours_rejected(client):
    data = schedule_form()
    data["d2_work_end"] = ""
    resp = client.post("/schedule/", data=data, follow_redirects=True)
    assert b"both work start and end" in resp.data
