"""Simple API helper used by the CLI and GUI."""

from __future__ import annotations

import os
import logging
from typing import Optional

import requests

LOG_FILE = os.path.join(os.path.dirname(__file__), 'csfloat.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)
logger = logging.getLogger(__name__)


def get_lowest_price(api_key: str, item_name: str) -> Optional[float]:
    """Return the lowest price for ``item_name`` in USD or ``None``."""
    url = "https://csfloat.com/api/v1/listings"
    params = {
        "market_hash_name": item_name,
        "limit": 1,
        "sort_by": "lowest_price",
    }
    headers = {"Authorization": api_key}

    logger.info("Requesting single price: params=%s", params)

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        logger.info("Response status: %s", response.status_code)
        response.raise_for_status()
        logger.info("Response body: %s", response.text[:200])
        data = response.json()
        if isinstance(data, list) and data:
            price_cents = data[0].get("price")
        elif isinstance(data, dict) and data.get("listings"):
            price_cents = data["listings"][0].get("price")
        else:
            price_cents = None

        if isinstance(price_cents, (int, float)):
            return price_cents / 100
        return None
    except requests.RequestException as exc:
        logger.exception("Failed to fetch price: %s", exc)
        return None


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
