"""Skinport public price feed.

Skinport exposes `GET /v1/items` without authentication — every CS2 item
with its current lowest listing price and quantity. Their edge cache holds
responses for 5 minutes and the endpoint REQUIRES Brotli
(``Accept-Encoding: br``); requests without it get a 406. httpx handles
decompression transparently once the ``brotli`` package is installed.

Docs: https://docs.skinport.com/items
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from .errors import NetworkError, UpstreamError

logger = logging.getLogger(__name__)

ITEMS_URL = "https://api.skinport.com/v1/items"
MIN_REFRESH_SECONDS = 900  # be politer than their 5-minute cache floor


async def fetch_skinport_items(*, timeout: float = 60.0) -> list[dict[str, Any]]:
    """All CS2 items with min price (converted to cents) and quantity."""
    headers = {
        "Accept-Encoding": "br",
        "User-Agent": "csfloat-tracker (+https://github.com/MhmdMK277/CSFloatPriceChecker)",
    }
    params = {"app_id": 730, "currency": "USD"}
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as http:
            resp = await http.get(ITEMS_URL, params=params)
    except httpx.HTTPError as exc:
        raise NetworkError("Could not reach Skinport.") from exc

    if resp.status_code == 406:
        raise UpstreamError(
            "Skinport rejected the request (Brotli support missing — is the "
            "'brotli' package installed?)", status=502,
        )
    if resp.status_code != 200:
        raise UpstreamError(f"Skinport returned {resp.status_code}.", status=502)

    now = datetime.now(UTC).isoformat()
    rows = []
    for item in resp.json():
        name = item.get("market_hash_name")
        min_price = item.get("min_price")  # dollars or None when unlisted
        if not name or min_price is None:
            continue
        rows.append({
            "market_hash_name": name,
            "min_price_cents": round(float(min_price) * 100),
            "quantity": item.get("quantity") or 0,
            "updated_at": now,
        })
    logger.info("Skinport feed: %d priced items", len(rows))
    return rows
