"""Starter data, inserted only into empty tables."""

# weekday, wake, work_start, work_end, commute, gym, effort, away
SCHEDULE = [
    (0, "07:00", "09:00", "18:00", 40, 1, "low", 0),
    (1, "07:00", "09:00", "18:00", 40, 0, "low", 0),
    (2, "07:00", "09:00", "18:00", 40, 1, "low", 0),
    (3, "07:00", "09:00", "18:00", 40, 0, "low", 0),
    (4, "07:00", "09:00", "18:00", 40, 1, "low", 0),
    (5, "08:30", None, None, 0, 0, "full", 0),
    (6, "08:30", None, None, 0, 0, "full", 0),
]


def _empty(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def seed(conn):
    if _empty(conn, "settings"):
        conn.execute("INSERT INTO settings (id) VALUES (1)")
    if _empty(conn, "schedule_days"):
        conn.executemany(
            "INSERT INTO schedule_days (weekday, wake, work_start, work_end, commute_min, gym, effort, away)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            SCHEDULE,
        )
