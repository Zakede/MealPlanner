from werkzeug.security import generate_password_hash

from mealplanner.views import auth


def test_site_gate_guards_everything(profile, client, monkeypatch):
    monkeypatch.setenv("MEALPLANNER_SITE_PASSWORD_HASH", generate_password_hash("hunter22"))
    auth._tries.clear()
    for path in ("/", "/people/", "/settings/", "/api/nudges"):
        r = client.get(path)
        assert r.status_code == 302 and "/gate" in r.headers["Location"], path
    assert client.post("/gate", data={"password": "nope"}).status_code == 200
    r = client.post("/gate?next=/settings/", data={"password": "hunter22"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/settings/")
    assert client.get("/settings/").status_code == 200


def test_site_gate_locks_after_five_wrong(profile, client, monkeypatch):
    monkeypatch.setenv("MEALPLANNER_SITE_PASSWORD_HASH", generate_password_hash("hunter22"))
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    auth._tries.clear()
    for _ in range(5):
        client.post("/gate", data={"password": "wrong"})
    page = client.post("/gate", data={"password": "hunter22"}).get_data(as_text=True)
    assert "Too many wrong tries" in page
    assert client.get("/").status_code == 302


def test_no_gate_when_not_set(profile, client, monkeypatch):
    monkeypatch.delenv("MEALPLANNER_SITE_PASSWORD_HASH", raising=False)
    assert client.get("/gate").status_code == 302


def test_gate_works_after_someone_set_up(profile, monkeypatch):
    # a new phone on the live site: password first, then "who's eating?", never a loop
    from werkzeug.security import generate_password_hash
    from mealplanner.views import auth
    monkeypatch.setenv("MEALPLANNER_SITE_PASSWORD_HASH", generate_password_hash("open sesame"))
    monkeypatch.setattr(auth, "_tries", {})      # earlier tests lock out the test address
    phone = profile.test_client()
    r = phone.get("/")
    assert "/gate" in r.headers["Location"]
    assert phone.get("/gate").status_code == 200
    r = phone.post("/gate", data={"password": "open sesame"})
    assert r.status_code == 302
    seen = []
    url = r.headers["Location"]
    for _ in range(5):
        r = phone.get(url)
        seen.append(url)
        if r.status_code != 302:
            break
        url = r.headers["Location"]
    assert r.status_code == 200 and "/people/" in seen[-1], seen
