"""Header-aware rate limiting for the CSFloat API.

CSFloat enforces per-endpoint buckets (N requests per rolling window) and
reports state via ``X-RateLimit-Limit`` / ``X-RateLimit-Remaining`` /
``X-RateLimit-Reset`` headers. We track each bucket, pre-emptively wait when
a bucket is empty, and expose a snapshot for the UI.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class Bucket:
    limit: int | None = None
    remaining: int | None = None
    reset_at: float | None = None  # unix epoch seconds
    last_request_at: float = 0.0
    requests_made: int = 0

    def snapshot(self) -> dict:
        wait = max(0.0, (self.reset_at or 0) - time.time()) if self.reset_at else 0.0
        return {
            "limit": self.limit,
            "remaining": self.remaining,
            "resets_in_seconds": round(wait, 1),
            "requests_made": self.requests_made,
        }


@dataclass
class RateLimiter:
    """Tracks CSFloat bucket state and gates outgoing requests.

    ``max_wait`` bounds how long :meth:`acquire` will sleep for an empty
    bucket before raising, so callers never hang for a full 5-minute window
    unless they opted into it.
    """

    max_wait: float = 30.0
    min_interval: float = 0.0  # optional politeness gap between requests per bucket
    _buckets: dict[str, Bucket] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def bucket(self, key: str) -> Bucket:
        return self._buckets.setdefault(key, Bucket())

    async def acquire(self, key: str) -> None:
        """Wait until a request on ``key`` is allowed.

        Raises
        ------
        RateLimitError
            If the bucket is exhausted and the reset is further away than
            ``max_wait``.
        """
        from .errors import RateLimitError

        async with self._lock:
            b = self.bucket(key)
            now = time.time()

            if b.remaining is not None and b.remaining <= 0 and b.reset_at:
                wait = b.reset_at - now
                if wait > self.max_wait:
                    raise RateLimitError(retry_after=wait)
                if wait > 0:
                    await asyncio.sleep(wait)
                b.remaining = None  # window rolled over; trust headers on next response

            if self.min_interval > 0:
                gap = self.min_interval - (time.time() - b.last_request_at)
                if gap > 0:
                    await asyncio.sleep(gap)

            b.last_request_at = time.time()
            b.requests_made += 1
            if b.remaining is not None:
                b.remaining -= 1

    def update(self, key: str, headers) -> None:
        """Record bucket state from CSFloat response headers."""
        b = self.bucket(key)
        try:
            if "x-ratelimit-limit" in headers:
                b.limit = int(headers["x-ratelimit-limit"])
            if "x-ratelimit-remaining" in headers:
                b.remaining = int(headers["x-ratelimit-remaining"])
            if "x-ratelimit-reset" in headers:
                reset = float(headers["x-ratelimit-reset"])
                # Header may be an epoch timestamp or a delta in seconds.
                b.reset_at = reset if reset > 1e9 else time.time() + reset
        except (TypeError, ValueError):
            pass

    def retry_after(self, key: str, headers) -> float:
        """Best-effort wait time after a 429, from headers or bucket state."""
        try:
            if "retry-after" in headers:
                return max(1.0, float(headers["retry-after"]))
        except (TypeError, ValueError):
            pass
        b = self.bucket(key)
        if b.reset_at:
            return max(1.0, b.reset_at - time.time())
        return 5.0

    def status(self) -> dict[str, dict]:
        return {key: b.snapshot() for key, b in self._buckets.items()}
