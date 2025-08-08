"""API helpers for CSFloat price checking."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

import requests

LOG_FILE = os.path.join(os.path.dirname(__file__), "csfloat.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / rate limit tracking
# ---------------------------------------------------------------------------

REQUEST_TIMES: list[float] = []
API_RATE_LIMIT: int = 60
RATE_LIMIT_HIT: bool = False


def update_rate_limit(headers: dict) -> None:
    """Update the global API rate limit from response headers."""
    global API_RATE_LIMIT
    try:
        limit = int(headers.get("X-RateLimit-Limit", API_RATE_LIMIT))
        if limit > 0:
            API_RATE_LIMIT = limit
    except (TypeError, ValueError):
        pass


def rate_limit_interval() -> float:
    """Return the recommended delay between requests based on the limit."""
    return 60.0 / API_RATE_LIMIT if API_RATE_LIMIT else 6.0


def record_request() -> None:
    """Record a request timestamp and prune entries older than a minute."""
    now = time.time()
    REQUEST_TIMES.append(now)
    while REQUEST_TIMES and now - REQUEST_TIMES[0] > 60:
        REQUEST_TIMES.pop(0)


# ---------------------------------------------------------------------------
# Low level query helpers
# ---------------------------------------------------------------------------

def query_listings(api_key: str, params: dict) -> Optional[Any]:
    """Query the CSFloat listings endpoint.

    Parameters
    ----------
    api_key:
        CSFloat API key.
    params:
        Parameters passed directly to the API.
    """

    url = "https://csfloat.com/api/v1/listings"
    params = params.copy()
    params.setdefault("limit", 50)
    headers = {"Authorization": api_key}

    logger.info("Request params: %s", params)

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        record_request()
        update_rate_limit(resp.headers)
        global RATE_LIMIT_HIT
        RATE_LIMIT_HIT = resp.status_code == 429
        logger.info("Response status: %s", resp.status_code)
        if RATE_LIMIT_HIT:
            return None
        resp.raise_for_status()
        logger.info("Response body: %s", resp.text[:200])
        return resp.json()
    except requests.RequestException as exc:
        logger.exception("Failed to query API: %s", exc)
        return None


def fetch_lowest_listing(api_key: str, item_name: str, filters: dict) -> Optional[dict]:
    """Return the lowest priced listing for ``item_name``.

    Parameters
    ----------
    api_key:
        CSFloat API key.
    item_name:
        Name of the item to search for.
    filters:
        Dictionary of additional query parameters and local flags. Supports an
        ``include_auctions`` boolean which, when ``False``, removes auction
        listings from the results.

    Returns
    -------
    dict | None
        A dictionary containing ``item``, ``price_usd``, ``url``,
        ``listing_id`` and ``is_auction`` keys, or ``None`` if no listings are
        found after applying filters.
    """

    params = filters.copy()
    include_auctions = params.pop("include_auctions", True)
    params["market_hash_name"] = item_name
    if not include_auctions:
        params["type"] = "buy_now"

    data = query_listings(api_key, params)
    if not data:
        return None

    listings = data.get("data") if isinstance(data, dict) else data
    if not listings:
        return None

    min_float = params.get("min_float")
    max_float = params.get("max_float")

    candidates: list[tuple[float, dict, bool]] = []
    for item in listings:
        price_cents = item.get("price")
        float_val = item.get("float", {}).get("float_value")
        is_auction = (
            item.get("is_auction")
            or item.get("auction") is True
            or item.get("listing_type") == "auction"
            or item.get("sale_type") == "auction"
            or item.get("type") == "auction"
        )
        if not include_auctions and is_auction:
            continue
        if isinstance(min_float, (int, float)) and (
            float_val is None or float_val < min_float
        ):
            continue
        if isinstance(max_float, (int, float)) and (
            float_val is None or float_val > max_float
        ):
            continue
        if isinstance(price_cents, (int, float)):
            candidates.append((price_cents, item, is_auction))

    if not candidates:
        return None

    price_cents, listing, is_auction = min(candidates, key=lambda x: x[0])
    price_usd = round(price_cents / 100, 2)
    listing_id = listing.get("id")
    url = f"https://csfloat.com/item/{listing_id}" if listing_id else ""

    return {
        "item": item_name,
        "price_usd": price_usd,
        "url": url,
        "listing_id": str(listing_id) if listing_id else "",
        "is_auction": bool(is_auction),
    }


def get_lowest_price(api_key: str, item_name: str) -> Optional[float]:
    """Return the lowest price for ``item_name`` in USD or ``None``."""
    res = fetch_lowest_listing(api_key, item_name, {})
    if res is None:
        return None
    return res.get("price_usd")


def main() -> None:
    """Standalone entry point for one-off price checks."""
    key = input("Enter your CSFloat API key: ").strip()
    if not key:
        print("API key is required.")
        return

    item_name = input("Enter the item name to check price for: ").strip()
    if not item_name:
        print("Item name is required.")
        return

    price = get_lowest_price(key, item_name)
    if price is None:
        print(f"No price information found for '{item_name}'.")
    else:
        print(f"Lowest price for '{item_name}' is ${price:.2f}.")


if __name__ == "__main__":
    main()

