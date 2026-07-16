"""Steam inventory import: JSON dumps and public inventory fetch.

Supports two sources:
- an uploaded Steam inventory JSON dump (``assets`` + ``descriptions``)
- a live fetch of a public inventory by SteamID64 (no Steam API key needed)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from .errors import NetworkError, NotFoundError, UpstreamError

logger = logging.getLogger(__name__)

STEAM_INVENTORY_URL = "https://steamcommunity.com/inventory/{steam_id}/730/2"

WEAR_ABBREVIATIONS = {
    "Factory New": "FN",
    "Minimal Wear": "MW",
    "Field-Tested": "FT",
    "Well-Worn": "WW",
    "Battle-Scarred": "BS",
}

# Item types that have no market value worth pricing (rank badges, service
# medals and the like are usually untradable).
IGNORED_TYPE_SUBSTRINGS = ("badge", "medal", "coin", "trophy")


@dataclass
class InventoryItem:
    market_hash_name: str
    wear: str | None
    item_type: str
    rarity_color: str | None
    icon_url: str | None
    marketable: bool
    quantity: int = 1


def _extract_wear(tags: list[dict[str, Any]]) -> str | None:
    for tag in tags:
        if tag.get("category") == "Exterior":
            return WEAR_ABBREVIATIONS.get(tag.get("localized_tag_name") or "")
    return None


def parse_inventory(data: dict[str, Any]) -> list[InventoryItem]:
    """Parse a Steam inventory payload into deduplicated priced-item rows."""
    assets = data.get("assets") or []
    descriptions = data.get("descriptions") or []
    desc_map = {(d.get("classid"), d.get("instanceid")): d for d in descriptions}

    counted: dict[str, InventoryItem] = {}
    for asset in assets:
        desc = desc_map.get((asset.get("classid"), asset.get("instanceid")))
        if not desc:
            continue
        item_type = str(desc.get("type", ""))
        if any(sub in item_type.lower() for sub in IGNORED_TYPE_SUBSTRINGS):
            continue
        name = desc.get("market_hash_name") or desc.get("name")
        if not name:
            continue
        if name in counted:
            counted[name].quantity += 1
            continue
        counted[name] = InventoryItem(
            market_hash_name=name,
            wear=_extract_wear(desc.get("tags") or []),
            item_type=item_type,
            rarity_color=desc.get("name_color"),
            icon_url=desc.get("icon_url"),
            marketable=bool(desc.get("marketable", 1)),
        )
    return list(counted.values())


async def fetch_steam_inventory(steam_id: str, *, timeout: float = 20.0) -> dict[str, Any]:
    """Download a public CS2 inventory from Steam.

    Steam paginates with ``last_assetid``; we follow up to a sane cap.
    Raises NotFoundError for private/missing inventories.
    """
    url = STEAM_INVENTORY_URL.format(steam_id=steam_id)
    merged: dict[str, Any] = {"assets": [], "descriptions": []}
    params: dict[str, Any] = {"l": "english", "count": 2000}

    async with httpx.AsyncClient(timeout=timeout) as http:
        for _ in range(10):  # cap at 20k items
            try:
                resp = await http.get(url, params=params)
            except httpx.HTTPError as exc:
                raise NetworkError("Could not reach Steam.") from exc
            if resp.status_code == 403:
                raise NotFoundError("That Steam inventory is private.")
            if resp.status_code == 429:
                raise UpstreamError("Steam is rate limiting inventory requests. Try again in a minute.", status=429)
            if resp.status_code != 200:
                raise UpstreamError(f"Steam returned {resp.status_code} for that inventory.")
            data = resp.json()
            if not data or not data.get("assets"):
                if not merged["assets"]:
                    raise NotFoundError("No CS2 items found — is the inventory public?")
                break
            merged["assets"].extend(data.get("assets") or [])
            merged["descriptions"].extend(data.get("descriptions") or [])
            if data.get("more_items") and data.get("last_assetid"):
                params["start_assetid"] = data["last_assetid"]
            else:
                break
    return merged
