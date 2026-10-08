"""Tiny in-memory rate limiter for the Gemini-backed endpoints.

Per process (so per Lambda instance) — enough to stop one visitor draining the
daily quota; AWS-side throttling can add a global limit on deploy.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit, window_s):
        self.limit = limit
        self.window = window_s
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:  # forget idle visitors
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True
