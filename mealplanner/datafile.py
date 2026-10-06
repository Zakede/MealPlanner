"""All of one profile's data as a plain JSON file, so it can be moved, read and fixed by hand.

  python -m mealplanner.datafile export zettai.json [--profile ID]
  python -m mealplanner.datafile import zettai.json [--profile ID]

The same format is used by Settings → Download backup / Restore backup.
"""
import json
import sys
from datetime import datetime

# the AI key stays out of files that get copied around
SKIP_COLUMNS = {"settings": {"gemini_key"}}


def _tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]


def dump(conn):
    data = {"app": "zettai", "exported": datetime.now().isoformat(timespec="seconds"), "tables": {}}
    for name in _tables(conn):
        skip = SKIP_COLUMNS.get(name, set())
        cur = conn.execute(f"SELECT * FROM {name}")
        cols = [c[0] for c in cur.description]
        data["tables"][name] = [{k: v for k, v in zip(cols, row) if k not in skip} for row in cur.fetchall()]
    return data


def load(conn, data):
    """Replace this profile's data with a dump. Tables or columns the app no longer has are ignored,
    missing columns get their defaults, and the current AI key is kept. All or nothing."""
    if not isinstance(data, dict) or not isinstance(data.get("tables"), dict):
        raise ValueError("that file isn't a Zettai backup")
    tables = data["tables"]
    if "settings" not in tables:
        raise ValueError("that backup has no settings table")
    row = conn.execute("SELECT gemini_key FROM settings WHERE id = 1").fetchone()
    key = row[0] if row else ""
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        for name in _tables(conn):
            if name not in tables:
                continue
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({name})")}
            conn.execute(f"DELETE FROM {name}")
            for item in tables[name]:
                if not isinstance(item, dict):
                    raise ValueError(f"a row in {name} isn't an object")
                keep = [k for k in item if k in cols]
                if keep:
                    conn.execute(f"INSERT INTO {name} ({', '.join(keep)}) VALUES ({', '.join('?' * len(keep))})",
                                 [item[k] for k in keep])
        if key:
            conn.execute("UPDATE settings SET gemini_key = ? WHERE id = 1 AND gemini_key = ''", (key,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise ValueError(f"restore failed, nothing was changed ({e})") from e
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _main(argv):
    if len(argv) < 2 or argv[0] not in ("export", "import"):
        sys.exit(__doc__)
    action, path = argv[0], argv[1]
    pid = argv[argv.index("--profile") + 1] if "--profile" in argv else "main"
    from . import create_app, profiles
    from .db import connect
    app = create_app()
    with app.app_context():
        person = profiles.find(pid)
        if not person:
            sys.exit(f"no profile {pid!r}; have: {', '.join(p['id'] for p in profiles.all_profiles())}")
        conn = connect(person["db"])
        if action == "export":
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(dump(conn), f, ensure_ascii=False, indent=1)
            print(f"Saved {person['name']}'s data to {path}")
        else:
            with open(path, encoding="utf-8") as f:
                load(conn, json.load(f))
            print(f"Loaded {path} into {person['name']}'s profile")
        conn.close()


if __name__ == "__main__":
    _main(sys.argv[1:])
