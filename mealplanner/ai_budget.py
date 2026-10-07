"""Keep AI use cheap: remember answers, and cap how many requests each person (and the site) makes a day.

One small SQLite file next to the profiles is shared by everyone, so an answer one person paid for is
free for the next. Photos are never cached.
"""
import hashlib
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import current_app

PER_PERSON_PER_DAY = int(os.environ.get("ZETTAI_AI_PER_PERSON", "40"))
SITE_PER_DAY = int(os.environ.get("ZETTAI_AI_SITE", "300"))
KEEP_DAYS = 30


def _db():
    path = Path(current_app.config["DATABASE"]).parent / "ai_cache.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, reply TEXT NOT NULL, created TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS usage (day TEXT NOT NULL, who TEXT NOT NULL, n INTEGER NOT NULL,"
                 " PRIMARY KEY (day, who))")
    return conn


def _who():
    try:
        from .profiles import current_id
        return current_id()
    except Exception:
        return "main"


def _today():
    from . import today
    return today()


def used_today(who=None):
    conn = _db()
    try:
        day = _today().isoformat()
        mine = conn.execute("SELECT n FROM usage WHERE day = ? AND who = ?", (day, who or _who())).fetchone()
        site = conn.execute("SELECT COALESCE(SUM(n), 0) FROM usage WHERE day = ?", (day,)).fetchone()
        return (mine[0] if mine else 0), site[0]
    finally:
        conn.close()


class Saver:
    """Wraps a provider: cached answers first, then the daily limits, then the real call."""

    def __init__(self, inner, use_cache=True):
        self.inner = inner
        self.use_cache = use_cache
        self.name = getattr(inner, "name", "")
        self.model = getattr(inner, "model", "")

    def fresh(self):
        """The same provider without the cache, for 'give me another one'."""
        return Saver(self.inner, use_cache=False)

    def complete(self, prompt, images=(), model=None):
        from .llm import LLMError
        key = hashlib.sha256(f"{model or self.model}\n{prompt}".encode()).hexdigest()
        conn = _db()
        try:
            if self.use_cache and not images:
                row = conn.execute("SELECT reply FROM cache WHERE key = ? AND created >= ?",
                                   (key, (_today() - timedelta(days=KEEP_DAYS)).isoformat())).fetchone()
                if row:
                    return row[0]
            day, who = _today().isoformat(), _who()
            mine = conn.execute("SELECT n FROM usage WHERE day = ? AND who = ?", (day, who)).fetchone()
            site = conn.execute("SELECT COALESCE(SUM(n), 0) FROM usage WHERE day = ?", (day,)).fetchone()[0]
            if (mine[0] if mine else 0) >= PER_PERSON_PER_DAY:
                raise LLMError(f"that's your {PER_PERSON_PER_DAY} AI requests for today. It resets tomorrow")
            if site >= SITE_PER_DAY:
                raise LLMError("the AI helper has done enough for everyone today. It resets tomorrow")
            reply = self.inner.complete(prompt, images=images, model=model) if images or model else \
                self.inner.complete(prompt)
            conn.execute("INSERT INTO usage (day, who, n) VALUES (?, ?, 1)"
                         " ON CONFLICT(day, who) DO UPDATE SET n = n + 1", (day, who))
            if not images and reply:
                conn.execute("INSERT OR REPLACE INTO cache (key, reply, created) VALUES (?, ?, ?)",
                             (key, reply, day))
            conn.execute("DELETE FROM cache WHERE created < ?", ((_today() - timedelta(days=KEEP_DAYS)).isoformat(),))
            conn.execute("DELETE FROM usage WHERE day < ?", ((_today() - timedelta(days=7)).isoformat(),))
            conn.commit()
            return reply
        finally:
            conn.close()


def fresh(p):
    """Skip the cache when the caller wants a new answer to the same question."""
    return p.fresh() if isinstance(p, Saver) else p
