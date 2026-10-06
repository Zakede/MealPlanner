from mealplanner import profiles, store
from mealplanner.db import query


def make_friend(client, name="Ken"):
    return client.post("/people/new", data={"name": name})


def test_single_profile_needs_no_picker(client):
    assert client.get("/more").status_code == 200


def test_new_profile_has_its_own_data(app, client):
    client.post("/settings/", data=__import__("tests.test_settings_view", fromlist=["form"]).form(age="41"))
    resp = make_friend(client)
    assert "/setup/" in resp.headers["Location"]
    with client.session_transaction() as sess:
        friend = sess["profile"]
    with app.test_request_context():
        from flask import session
        session["profile"] = friend
        assert store.settings()["age"] is None                 # fresh settings for Ken
        assert query("SELECT COUNT(*) c FROM recipes", one=True)["c"] > 30   # with the full library
    with app.app_context():
        assert store.settings()["age"] == 41                   # main profile untouched
        assert [p["name"] for p in profiles.all_profiles()] == ["Me", "Ken"]


def test_picker_shows_when_several_people(app, client):
    make_friend(client)
    other = app.test_client()
    resp = other.get("/")
    assert resp.status_code == 302 and "/people/" in resp.headers["Location"]
    page = other.get("/people/").data.decode()
    assert "Who&#39;s eating?" in page or "Who's eating?" in page
    assert "Ken" in page and "Me" in page
    other.post("/people/main/use")
    assert other.get("/more").status_code == 200


def test_each_profile_has_its_own_lock(app, client):
    make_friend(client)                       # client is now on Ken
    client.post("/lock", data={"password": "kenpass1", "again": "kenpass1"})
    phone = app.test_client()
    phone.post("/people/main/use")
    assert phone.get("/more").status_code == 200        # main has no password
    with client.session_transaction() as sess:
        ken = sess["profile"]
    phone.post(f"/people/{ken}/use")
    resp = phone.get("/more")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]
    phone.post("/login", data={"password": "kenpass1"})
    assert phone.get("/more").status_code == 200


def test_rename_and_delete(app, client):
    make_friend(client)
    with client.session_transaction() as sess:
        ken = sess["profile"]
    client.post(f"/people/{ken}/rename", data={"name": "Kenji"})
    with app.app_context():
        assert profiles.find(ken)["name"] == "Kenji"
    resp = client.post(f"/people/{ken}/delete", data={"confirm": "nope"}, follow_redirects=True)
    assert b"Nothing was deleted" in resp.data
    client.post(f"/people/{ken}/delete", data={"confirm": "DELETE"})
    with app.app_context():
        assert profiles.find(ken) is None and len(profiles.all_profiles()) == 1


def test_main_profile_cannot_be_deleted(client):
    resp = client.post("/people/main/delete", data={"confirm": "DELETE"}, follow_redirects=True)
    assert b"can&#39;t be deleted" in resp.data or b"can't be deleted" in resp.data


def test_duplicate_names_rejected(client):
    make_friend(client)
    client.post("/people/main/use")
    resp = client.post("/people/new", data={"name": "ken"}, follow_redirects=True)
    assert b"taken" in resp.data


def test_new_phone_never_lands_in_a_set_up_profile(profile):
    # someone set up the first profile; a second phone must be asked, not dropped into it
    phone = profile.test_client()
    resp = phone.get("/")
    assert resp.status_code == 302 and "/people/" in resp.headers["Location"]
    assert "I&#39;m new here" in phone.get("/people/").data.decode()
    resp = phone.post("/people/new", data={"name": "Aiko"})
    assert "/setup/" in resp.headers["Location"]
    phone.post("/setup/", data={"profile_name": "Aiko", "sex": "female", "age": "24", "height_cm": "160",
                                "weight_kg": "55", "goal_weight_kg": "52", "pace_kg_week": "0.3",
                                "training_days": "2", "weekly_budget_yen": "8000", "eat_out_slots": "1",
                                "eat_out_budget_yen": "1000", "spice_tolerance": "2"})
    with profile.app_context():
        assert store.settings()["age"] == 25 and store.settings()["sex"] == "male"   # first profile untouched
        assert [p["name"] for p in profiles.all_profiles()] == ["Me", "Aiko"]
