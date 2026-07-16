"""Small in-memory TTL cache for API responses.

Single-event-loop use only; no locking needed because entries are read and
written synchronously between awaits.
"""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    def __init__(self, max_entries: int = 512) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._max = max_entries

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires, value = entry
        if time.monotonic() >= expires:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: float) -> None:
        if ttl <= 0:
            return
        if len(self._store) >= self._max:
            self._evict()
        self._store[key] = (time.monotonic() + ttl, value)

    def _evict(self) -> None:
        """Drop expired entries; if still full, drop the soonest-expiring half."""
        now = time.monotonic()
        self._store = {k: v for k, v in self._store.items() if v[0] > now}
        if len(self._store) >= self._max:
            by_expiry = sorted(self._store.items(), key=lambda kv: kv[1][0])
            self._store = dict(by_expiry[len(by_expiry) // 2 :])

    def clear(self) -> None:
        self._store.clear()
