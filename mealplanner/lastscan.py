"""The last receipt or order the AI read, kept for a day.

Phones drop a slow request when the screen locks or you switch apps, after the server has already done
the reading. Keeping the result means coming back to the page shows it instead of starting over.
"""
import json
import os
import time

KEEP_SECONDS = 24 * 3600


def _path(kind):
    from .profiles import db_path
    return f"{db_path()}.last-{kind}.json"


def save(kind, **data):
    data["at"] = time.time()
    with open(_path(kind), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def load(kind):
    """The saved scan as a dict (with "minutes" since it was read), or None."""
    try:
        with open(_path(kind), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    age = time.time() - data.get("at", 0)
    if age > KEEP_SECONDS:
        clear(kind)
        return None
    data["minutes"] = int(age // 60)
    return data


def clear(kind):
    try:
        os.remove(_path(kind))
    except OSError:
        pass
