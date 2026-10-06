import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path):
    conn = sqlite3.connect(path, detect_types=0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        from .profiles import db_path
        g.db = connect(db_path())
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Columns added after the first release: (table, column, definition)
MIGRATIONS = [
    ("settings", "theme", "TEXT NOT NULL DEFAULT 'apothecary'"),
    ("settings", "mode", "TEXT NOT NULL DEFAULT 'dark'"),
    ("settings", "job", "TEXT NOT NULL DEFAULT 'desk'"),
    ("settings", "training_days", "INTEGER NOT NULL DEFAULT 3"),
    ("settings", "training_intensity", "TEXT NOT NULL DEFAULT 'moderate'"),
    ("settings", "diet", "TEXT NOT NULL DEFAULT 'any'"),
    ("settings", "avoid", "TEXT NOT NULL DEFAULT ''"),
    ("settings", "setup_done", "INTEGER NOT NULL DEFAULT 0"),
    ("foods", "category", "TEXT NOT NULL DEFAULT ''"),
    ("recipes", "builtin", "INTEGER NOT NULL DEFAULT 0"),
    ("recipes", "equipment", "TEXT NOT NULL DEFAULT ''"),
    ("settings", "schedule_mode", "TEXT NOT NULL DEFAULT 'fixed'"),
    ("settings", "prep_days", "INTEGER NOT NULL DEFAULT 2"),
    ("settings", "appliances", "TEXT NOT NULL DEFAULT 'stove,microwave,rice_cooker,freezer'"),
    ("settings", "about_me", "TEXT NOT NULL DEFAULT ''"),
    ("settings", "gemini_key", "TEXT NOT NULL DEFAULT ''"),
    ("settings", "country", "TEXT NOT NULL DEFAULT 'JP'"),
    ("settings", "area", "TEXT NOT NULL DEFAULT 'city'"),
    ("settings", "shop", "TEXT NOT NULL DEFAULT 'supermarket'"),
    ("settings", "goal_mode", "TEXT NOT NULL DEFAULT 'pace'"),
    ("settings", "deficit_kcal", "INTEGER NOT NULL DEFAULT 500"),
    ("settings", "protein_per_kg", "REAL NOT NULL DEFAULT 1.8"),
    ("settings", "fat_share", "REAL NOT NULL DEFAULT 0.25"),
    ("settings", "password_hash", "TEXT NOT NULL DEFAULT ''"),
    ("day_overrides", "work_mode", "TEXT"),
    ("day_overrides", "work_start", "TEXT"),
    ("day_overrides", "work_end", "TEXT"),
    ("day_overrides", "commute_min", "INTEGER"),
    ("day_overrides", "note", "TEXT"),
    ("day_overrides", "work_kind", "TEXT"),
    ("settings", "food_rules", "TEXT NOT NULL DEFAULT ''"),
    ("settings", "staples", "TEXT NOT NULL DEFAULT ''"),
    ("settings", "prep_weekdays", "TEXT NOT NULL DEFAULT ''"),
    ("settings", "prep_covers", "TEXT NOT NULL DEFAULT 'lunch'"),
    ("settings", "walking", "TEXT NOT NULL DEFAULT 'little'"),
]


def migrate(conn):
    for table, column, definition in MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db(conn):
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    migrate(conn)
    from .seed import seed
    seed(conn)
    conn.commit()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def reset_all(conn, keep_key=True):
    """Wipe every table and start fresh with the built-in library. Optionally keep the AI key."""
    key = ""
    if keep_key:
        row = conn.execute("SELECT gemini_key FROM settings WHERE id = 1").fetchone()
        key = row[0] if row else ""
    conn.execute("PRAGMA foreign_keys = OFF")
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    for t in tables:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    if key:
        conn.execute("UPDATE settings SET gemini_key = ? WHERE id = 1", (key,))
        conn.commit()
