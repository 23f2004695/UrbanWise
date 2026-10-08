"""Last good copy of each upstream response, for when a provider is busy.

Open-Meteo returns 429/503 under load and NASA FIRMS has short outages. Rather
than show an error, we serve the last good data (up to 6 h old) and say so:
payloads get a "stale" field and the dashboard shows how old the data is.
"""

import copy
import functools
import logging
import threading
from datetime import datetime, timezone

from cachetools import TTLCache

MAX_AGE_S = 6 * 3600

log = logging.getLogger(__name__)


class StaleList(list):
    """A list (e.g. fires) served from the last good copy."""
    stale_since = None


def _now():
    return datetime.now(timezone.utc)


def mark_stale(value, since):
    """A copy of `value` labelled with when it was really fetched (ISO string)."""
    if isinstance(value, dict):
        return {**value, "_stale_since": since}
    if isinstance(value, list):
        marked = StaleList(value)
    else:
        marked = copy.copy(value)
    marked.stale_since = since
    return marked


def stale_since(value):
    if isinstance(value, dict):
        return value.get("_stale_since")
    return getattr(value, "stale_since", None)


def stale_info(*values, now=None):
    """{"since", "age_min"} for the oldest stale input, or None if all are fresh."""
    sinces = [s for s in map(stale_since, values) if s]
    if not sinces:
        return None
    oldest = min(sinces)
    age = (now or _now()) - datetime.fromisoformat(oldest)
    return {"since": oldest, "age_min": max(0, round(age.total_seconds() / 60))}


def keep_last_good(name, errors, maxsize=500):
    """Decorator: on `errors`, return the last good result for the same arguments.

    Put it under @cached, so the normal cache still decides how often we fetch.
    """
    store = TTLCache(maxsize=maxsize, ttl=MAX_AGE_S)
    lock = threading.Lock()

    def decorate(fetch):
        @functools.wraps(fetch)
        def wrapper(*args):
            try:
                value = fetch(*args)
            except errors as exc:
                with lock:
                    saved = store.get(args)
                if saved is None:
                    raise
                value, since = saved
                log.warning("%s failed (%s); serving data from %s", name, exc, since)
                return mark_stale(value, since)
            with lock:
                store[args] = (value, _now().isoformat())
            return value

        wrapper.last_good = store  # for tests
        return wrapper

    return decorate
