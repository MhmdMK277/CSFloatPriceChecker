"""Steam inventory import: JSON dumps, manual paste, and public fetch.

Since Steam's April 2024 trade-hold update, a CS2 inventory spans two
contexts - 2 (tradable) and 16 (trade-protected for 10 days after a trade)
- and Steam rate-limits server-side inventory fetches aggressively. We
therefore support three sources:

- a live fetch of a public inventory by SteamID64 (works sometimes)
- manually pasted inventory JSON, per context, copied from the user's own
  browser session (reliable - the user is authenticated with Steam)
- an uploaded Steam inventory JSON dump
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .errors import NetworkError, NotFoundError, UpstreamError

logger = logging.getLogger(__name__)

STEAM_INVENTORY_URL = "https://steamcommunity.com/inventory/{steam_id}/730/{context}"
CONTEXT_TRADABLE = 2
CONTEXT_TRADE_PROTECTED = 16

_PROFILE_URL_RE = re.compile(r"^(?:https?://)?steamcommunity\.com/profiles/(\d{17})(?:[/?#].*)?$")
_VANITY_URL_RE = re.compile(r"^(?:https?://)?steamcommunity\.com/id/([^/?#]+)(?:[/?#].*)?$")


def parse_steam_input(value: str) -> tuple[str | None, str | None]:
    """Extract a SteamID64 from a raw id or any steamcommunity profile URL.

    Returns ``(steamid64, error_message)`` - exactly one side is set.
    Vanity URLs (/id/name) can't be resolved without a Steam Web API key,
    so they return a helpful error instead.
    """
    value = value.strip().rstrip("/")
    if not value:
        return None, "Enter a SteamID64 or Steam profile URL."

    if value.isdigit() and len(value) == 17:
        return value, None

    m = _PROFILE_URL_RE.match(value)
    if m:
        return m.group(1), None

    m = _VANITY_URL_RE.match(value)
    if m:
        return None, (
            f"Custom URL detected ('{m.group(1)}'). Steam doesn't expose the SteamID64 "
            "for custom URLs without an API key - look yours up at steamid.io and paste "
            "the 17-digit SteamID64, or use Manual Load below."
        )

    return None, "Unrecognized format. Enter a 17-digit SteamID64 or a steamcommunity.com profile URL."


def merge_inventory_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine inventory JSON payloads (e.g. contexts 2 and 16).

    Assets are deduplicated by (contextid, assetid); descriptions by
    (classid, instanceid). Also reports whether any payload looked
    truncated (Steam's ``more_items`` flag, or a total count larger than
    what the payload carried).
    """
    merged: dict[str, Any] = {"assets": [], "descriptions": []}
    seen_assets: set[tuple[str, str]] = set()
    seen_descs: set[tuple[str, str]] = set()
    truncated = False

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        assets = payload.get("assets") or []
        for asset in assets:
            key = (str(asset.get("contextid", "")), str(asset.get("assetid", id(asset))))
            if key not in seen_assets:
                seen_assets.add(key)
                merged["assets"].append(asset)
        for desc in payload.get("descriptions") or []:
            key = (str(desc.get("classid", "")), str(desc.get("instanceid", "")))
            if key not in seen_descs:
                seen_descs.add(key)
                merged["descriptions"].append(desc)
        total = payload.get("total_inventory_count")
        if payload.get("more_items") or (isinstance(total, int) and total > len(assets)):
            truncated = True

    merged["truncated"] = truncated
    return merged

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


async def fetch_steam_inventory(
    steam_id: str, *, context: int = CONTEXT_TRADABLE, timeout: float = 20.0
) -> dict[str, Any]:
    """Download a public CS2 inventory context from Steam.

    Steam paginates with ``last_assetid``; we follow up to a sane cap.
    Raises NotFoundError for private/missing inventories. Note: Steam
    rate-limits this endpoint heavily since April 2024 - callers should
    treat 429s as expected and offer the manual-paste path.
    """
    url = STEAM_INVENTORY_URL.format(steam_id=steam_id, context=context)
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
                raise UpstreamError(
                    "Steam is rate limiting inventory requests - use Manual Load below.",
                    status=429,
                )
            if resp.status_code != 200:
                raise UpstreamError(f"Steam returned {resp.status_code} for that inventory.")
            data = resp.json()
            if not data or not data.get("assets"):
                if not merged["assets"]:
                    raise NotFoundError("No CS2 items found - is the inventory public?")
                break
            merged["assets"].extend(data.get("assets") or [])
            merged["descriptions"].extend(data.get("descriptions") or [])
            if data.get("more_items") and data.get("last_assetid"):
                params["start_assetid"] = data["last_assetid"]
            else:
                break
    return merged


async def fetch_full_inventory(steam_id: str, *, timeout: float = 20.0) -> dict[str, Any]:
    """Fetch tradable (context 2) plus, best-effort, trade-protected (16).

    The tradable context is required; the trade-protected fetch spends a
    second rate-limited request, so failures there are swallowed - manual
    load covers that case.
    """
    tradable = await fetch_steam_inventory(steam_id, context=CONTEXT_TRADABLE, timeout=timeout)
    payloads = [tradable]
    try:
        protected = await fetch_steam_inventory(
            steam_id, context=CONTEXT_TRADE_PROTECTED, timeout=timeout
        )
        payloads.append(protected)
    except (NetworkError, NotFoundError, UpstreamError) as exc:
        logger.info("Trade-protected context fetch skipped: %s", exc)
    return merge_inventory_payloads(payloads)


def context_counts(data: dict[str, Any]) -> dict[str, int]:
    """Per-context asset counts for a merged payload."""
    counts = {"tradable": 0, "trade_protected": 0, "other": 0}
    for asset in data.get("assets") or []:
        ctx = str(asset.get("contextid", ""))
        if ctx == str(CONTEXT_TRADABLE):
            counts["tradable"] += 1
        elif ctx == str(CONTEXT_TRADE_PROTECTED):
            counts["trade_protected"] += 1
        else:
            counts["other"] += 1
    return counts
