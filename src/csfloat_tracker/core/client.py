"""Async CSFloat API client with rate limiting, retries and caching.

Usage::

    async with CSFloatClient(api_key="...") as client:
        page = await client.get_listings(market_hash_name="AK-47 | Redline (Field-Tested)")
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from typing import Any

import httpx

from .cache import TTLCache
from .errors import AuthError, NetworkError, NotFoundError, RateLimitError, UpstreamError
from .models import Listing
from .ratelimit import RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://csfloat.com/api/v1"
USER_AGENT = "csfloat-tracker/1.0 (+https://github.com/MhmdMK277/CSFloatPriceChecker)"

# Query params /listings accepts; anything else is dropped before sending.
LISTING_PARAMS = {
    "market_hash_name", "min_float", "max_float", "min_price", "max_price",
    "category", "sort_by", "type", "limit", "page", "cursor",
    "def_index", "paint_index", "paint_seed", "collection", "min_ref_qty",
    "stickers", "keychains", "rarity", "min_blue_gem", "max_blue_gem",
}

SORT_OPTIONS = {
    "lowest_price", "highest_price", "most_recent", "expires_soon",
    "lowest_float", "highest_float", "best_deal", "highest_discount",
    "float_rank", "num_bids",
}


class ListingsPage:
    """A page of listings plus the cursor CSFloat returned for the next page."""

    __slots__ = ("cursor", "listings")

    def __init__(self, listings: list[Listing], cursor: str | None) -> None:
        self.listings = listings
        self.cursor = cursor


class CSFloatClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = 20.0,
        max_retries: int = 3,
        limiter: RateLimiter | None = None,
        cache: TTLCache | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.limiter = limiter or RateLimiter()
        self.cache = cache or TTLCache()
        headers = {"User-Agent": USER_AGENT}
        self._http = httpx.AsyncClient(
            timeout=timeout, headers=headers, transport=transport, follow_redirects=True
        )

    async def __aenter__(self) -> CSFloatClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Low-level request machinery
    # ------------------------------------------------------------------

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        cache_ttl: float = 0.0,
        authenticated: bool = True,
    ) -> Any:
        cache_key = f"{path}?{sorted((params or {}).items())!r}"
        if cache_ttl > 0:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        headers = {}
        if authenticated and self.api_key:
            headers["Authorization"] = self.api_key

        bucket = path.lstrip("/").split("/")[0]
        url = f"{self.base_url}/{path.lstrip('/')}"

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            await self.limiter.acquire(bucket)
            try:
                resp = await self._http.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                last_error = NetworkError()
                logger.warning("Network error calling %s (attempt %d): %s", path, attempt + 1, exc)
                await self._backoff(attempt)
                continue

            self.limiter.update(bucket, resp.headers)

            if resp.status_code in (401, 403):
                raise AuthError()
            if resp.status_code == 404:
                raise NotFoundError()
            if resp.status_code == 429:
                wait = self.limiter.retry_after(bucket, resp.headers)
                if attempt >= self.max_retries or wait > self.limiter.max_wait:
                    raise RateLimitError(retry_after=wait)
                logger.info("429 from CSFloat on %s; backing off %.1fs", path, wait)
                await asyncio.sleep(wait + random.uniform(0, 0.5))
                continue
            if resp.status_code >= 500:
                last_error = UpstreamError(status=resp.status_code)
                logger.warning("CSFloat %d on %s (attempt %d)", resp.status_code, path, attempt + 1)
                await self._backoff(attempt)
                continue
            if resp.status_code >= 400:
                detail = ""
                with contextlib.suppress(Exception):
                    detail = resp.json().get("message") or resp.json().get("code") or ""
                raise UpstreamError(f"CSFloat rejected the request ({resp.status_code}). {detail}".strip(), status=400)

            try:
                data = resp.json()
            except ValueError as exc:
                raise UpstreamError("CSFloat returned a malformed response.") from exc

            if cache_ttl > 0:
                self.cache.set(cache_key, data, cache_ttl)
            return data

        raise last_error or UpstreamError()

    async def _backoff(self, attempt: int) -> None:
        if attempt < self.max_retries:
            await asyncio.sleep(min(8.0, (2**attempt) * 0.5) + random.uniform(0, 0.25))

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    async def get_listings(self, *, cache_ttl: float = 0.0, **filters: Any) -> ListingsPage:
        """Fetch active listings. Prices in filters are integer cents."""
        params = {k: v for k, v in filters.items() if k in LISTING_PARAMS and v is not None}
        params.setdefault("limit", 50)
        if "sort_by" in params and params["sort_by"] not in SORT_OPTIONS:
            del params["sort_by"]
        data = await self._request("listings", params, cache_ttl=cache_ttl)
        # The API has returned both a bare list and {"data": [...], "cursor": ...}
        if isinstance(data, list):
            raw_listings, cursor = data, None
        else:
            raw_listings = data.get("data") or []
            cursor = data.get("cursor")
        return ListingsPage([Listing.from_api(x) for x in raw_listings], cursor)

    async def get_listing(self, listing_id: str) -> Listing:
        data = await self._request(f"listings/{listing_id}")
        return Listing.from_api(data)

    async def get_schema(self) -> dict[str, Any]:
        """Full CS2 item schema (weapons, paints, stickers, reference prices).

        Public endpoint; cached aggressively since it changes rarely.
        """
        return await self._request("schema", cache_ttl=3600.0, authenticated=False)

    async def get_me(self) -> dict[str, Any]:
        """Profile of the authenticated user; used to validate API keys."""
        return await self._request("me")

    async def validate_key(self) -> dict[str, Any] | None:
        """Return basic profile info if the key works, else raise AuthError."""
        if not self.api_key:
            raise AuthError("No API key configured.")
        data = await self.get_me()
        user = data.get("user") or data
        return {"username": user.get("username"), "steam_id": user.get("steam_id")}

    async def get_exchange_rates(self) -> dict[str, Any]:
        return await self._request("meta/exchange-rates", cache_ttl=3600.0, authenticated=False)

    def rate_status(self) -> dict[str, dict]:
        """Per-endpoint rate bucket snapshots for the UI."""
        return self.limiter.status()
