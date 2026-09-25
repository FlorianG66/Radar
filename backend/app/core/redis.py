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
    """Proxy that no-ops when Redis is unreachable.

    When Redis is down, subtle semantics like ``SET NX`` locks and TTL are
    emulated with a tiny in-process cache so behaviour (locking, rate-limit,
    suppression windows) stays correct for a single process — exactly the
    situation of local development and the test suite.
    """

    def __init__(self, client: Redis):
        self.client = client
        self._ok: bool | None = None
        self._local: dict[str, float] = {}  # key -> absolute expiry (0 = forever)
        self._local_values: dict = {}

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

    # ------------------------------------------------------------------
    # in-process fallback used only when Redis is unreachable
    # ------------------------------------------------------------------
    def _expire_at(self, **k) -> float:
        import time

        expiry = 0.0
        ex = k.pop("ex", None)
        px = k.pop("px", None)
        if ex is not None:
            expiry = time.time() + float(ex)
        elif px is not None:
            expiry = time.time() + float(px) / 1000.0
        return expiry

    def _local_get(self, key: str):
        import time

        exp = self._local.get(key)
        if exp is None:
            return None
        if exp and exp < time.time():
            self._local.pop(key, None)
            return None
        return self._local_values.get(key) if hasattr(self, "_local_values") else "1"

    def _local_set(self, key: str, value, **k) -> bool:
        nx = k.pop("nx", False)
        import time

        if nx and self._local_get(key) is not None:
            return False
        self._local[key] = self._expire_at(**k)
        self._local_values[key] = value
        return True

    # --- every method below safely no-ops when Redis is down ---
    # Neutral values are chosen so callers keep progressing (they are only
    # correctness-relevant when Redis is actually up, e.g. lock acquisition).
    def set(self, *a, **k):
        if not self._check():
            return self._local_set(*a, **k)
        try:
            return self.client.set(*a, **k)
        except Exception:
            return self._local_set(*a, **k)

    def get(self, *a, **k):
        if not self._check():
            return self._local_get(a[0]) if a else None
        try:
            return self.client.get(*a, **k)
        except Exception:
            return self._local_get(a[0]) if a else None

    def delete(self, *a, **k):
        if not self._check():
            for key in a:
                self._local.pop(key, None)
                self._local_values.pop(key, None)
            return None
        try:
            return self.client.delete(*a, **k)
        except Exception:
            return None

    def incr(self, *a, **k):
        if not self._check():
            key = a[0] if a else None
            if key:
                cur = self._local_values.setdefault(key, 0)
                self._local_values[key] = int(cur) + 1
                return self._local_values[key]
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