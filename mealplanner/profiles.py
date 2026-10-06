"""People who use the app. Each profile is its own SQLite file, so data never mixes.

The original database is the "main" profile; others live in <instance>/profiles/<id>.db and are
listed in <instance>/profiles.json.
"""
import json
import re
import secrets
from pathlib import Path

from flask import current_app, has_request_context, session

MAIN = "main"


def _dir():
    return Path(current_app.config["DATABASE"]).parent


def _registry_path():
    return _dir() / "profiles.json"


def all_profiles():
    """[{id, name, db}], main first."""
    path = _registry_path()
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    people = [{"id": MAIN, "name": data.get(MAIN, {}).get("name", "Me"), "db": current_app.config["DATABASE"]}]
    for pid, info in data.items():
        if pid == MAIN:
            continue
        people.append({"id": pid, "name": info["name"], "db": str(_dir() / "profiles" / f"{pid}.db")})
    return people


def _save(people):
    data = {p["id"]: {"name": p["name"]} for p in people}
    _registry_path().write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def main_set_up():
    """Has someone already set up the first profile? Then a new phone must pick or add a person,
    instead of landing in (and overwriting) that profile."""
    from .db import connect
    conn = connect(current_app.config["DATABASE"])
    try:
        row = conn.execute("SELECT setup_done FROM settings WHERE id = 1").fetchone()
    finally:
        conn.close()
    return bool(row and row[0])


def find(pid):
    return next((p for p in all_profiles() if p["id"] == pid), None)


def current_id():
    if has_request_context():
        pid = session.get("profile")
        if pid and find(pid):
            return pid
    return MAIN


def current():
    return find(current_id())


def db_path():
    return find(current_id())["db"]


def create(name):
    from .db import connect, init_db
    name = name.strip()[:30]
    if not name:
        raise ValueError("give the profile a name")
    people = all_profiles()
    if any(p["name"].lower() == name.lower() for p in people):
        raise ValueError("that name is taken")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:16] or "person"
    pid = f"{slug}-{secrets.token_hex(3)}"
    (_dir() / "profiles").mkdir(exist_ok=True)
    people.append({"id": pid, "name": name, "db": str(_dir() / "profiles" / f"{pid}.db")})
    conn = connect(people[-1]["db"])
    init_db(conn)
    conn.close()
    _save(people)
    return pid


def rename(pid, name):
    name = name.strip()[:30]
    if not name:
        raise ValueError("give the profile a name")
    people = all_profiles()
    for p in people:
        if p["id"] == pid:
            p["name"] = name
    _save(people)


def delete(pid):
    if pid == MAIN:
        raise ValueError("the first profile can't be deleted, but it can be reset")
    people = all_profiles()
    target = next((p for p in people if p["id"] == pid), None)
    if not target:
        return
    _save([p for p in people if p["id"] != pid])
    Path(target["db"]).unlink(missing_ok=True)


def migrate_all():
    """Bring every profile's database up to date at startup."""
    from .db import connect, init_db
    for p in all_profiles()[1:]:
        if Path(p["db"]).exists():
            conn = connect(p["db"])
            init_db(conn)
            conn.close()
