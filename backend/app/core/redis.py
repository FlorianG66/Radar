"""Redis connection used by rate limiting, queue and scheduler.

A ``SafeRedis`` wrapper degrades gracefully when Redis is unavailable (pure
local development): every call returns a neutral value instead of raising,
so the API/workers keep running without Redis.
"""
from __future__ import annotations

import time

from redis import Redis

from app.core.config import get_settings

settings = get_settings()


class SafeRedis:
    """Proxy that no-ops when Redis is unreachable."""

    def __init__(self, client: Redis):
        self.client = client
        self._ok: bool | None = None

    def _available(self) -> bool:
        if self._ok is not None:
            return self._ok
        try:
            self.client.ping()
            self._ok = True
        except Exception:
            self._ok = False
        return self._ok

    def available(self) -> bool:
        return self._available()

    def _check(self) -> bool:
        if not self._available():
            # re-check occasionally in case Redis comes up later
            if self._ok is False and int(time.time()) % 30 == 0:
                self._ok = None
            return False
        return True

    # --- every method below safely no-ops when Redis is down ---
    def set(self, *a, **k):
        if not self._check():
            return None
        try:
            return self.client.set(*a, **k)
        except Exception:
            return None

    def get(self, *a, **k):
        if not self._check():
            return None
        try:
            return self.client.get(*a, **k)
        except Exception:
            return None

    def delete(self, *a, **k):
        if not self._check():
            return None
        try:
            return self.client.delete(*a, **k)
        except Exception:
            return None

    def incr(self, *a, **k):
        if not self._check():
            return 0
        try:
            return self.client.incr(*a, **k)
        except Exception:
            return 0

    def expire(self, *a, **k):
        if not self._check():
            return None
        try:
            return self.client.expire(*a, **k)
        except Exception:
            return None

    def keys(self, *a, **k):
        if not self._check():
            return []
        try:
            return self.client.keys(*a, **k)
        except Exception:
            return []

    def ping(self):
        return self._available()


redis_client = SafeRedis(Redis.from_url(settings.REDIS_URL, decode_responses=True))

try:  # RQ queues are only usable when Redis is up
    from rq import Queue

    scrape_queue = Queue("scrapes", connection=redis_client.client)  # type: ignore[arg-type]
    notification_queue = Queue("notifications", connection=redis_client.client)  # type: ignore[arg-type]
except Exception:  # pragma: no cover
    scrape_queue = None  # type: ignore[assignment]
    notification_queue = None  # type: ignore[assignment]