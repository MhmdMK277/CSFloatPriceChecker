"""Helpers for loading Steam inventory dumps."""
from __future__ import annotations

from typing import Dict, List, Tuple

# Map full wear names to abbreviated codes used by CSFloat API
WEAR_ABBREVIATIONS = {
    "Factory New": "FN",
    "Minimal Wear": "MW",
    "Field-Tested": "FT",
    "Well-Worn": "WW",
    "Battle-Scarred": "BS",
}

# Substrings that identify items which should be ignored when processing an
# inventory.  These include badges, medals, coins and other non-marketable
# collectibles that the user does not want priced.
IGNORED_TYPES = [
    "badge",
    "medal",
    "coin",
    "collectible",
    "music kit",
    "graffiti",
    "charm",
]


def _is_ignored(item: Dict) -> bool:
    """Return ``True`` if the item should be ignored based on its type."""
    item_type = str(item.get("type", "")).lower()
    return any(sub in item_type for sub in IGNORED_TYPES)


def _extract_wear(tags: List[Dict]) -> str | None:
    """Extract the wear code (FN/MW/FT/WW/BS) from a tag list."""
    for tag in tags:
        if tag.get("category") == "Exterior":
            full = tag.get("localized_tag_name")
            return WEAR_ABBREVIATIONS.get(full)
    return None


def parse_inventory(data: Dict) -> List[Tuple[str, str | None]]:
    """Parse a Steam inventory JSON dump.

    Parameters
    ----------
    data:
        The deserialised inventory JSON with ``assets`` and ``descriptions``
        sections as provided by the Steam API.

    Returns
    -------
    list
        A list of ``(market_hash_name, wear)`` tuples.  Items whose type
        matches entries in :data:`IGNORED_TYPES` are skipped.
    """

    assets = data.get("assets", [])
    descriptions = data.get("descriptions", [])
    desc_map = {(d.get("classid"), d.get("instanceid")): d for d in descriptions}

    items: List[Tuple[str, str | None]] = []
    for asset in assets:
        key = (asset.get("classid"), asset.get("instanceid"))
        desc = desc_map.get(key)
        if not desc:
            continue
        if _is_ignored(desc):
            continue
        name = desc.get("market_hash_name") or desc.get("name")
        if not name:
            continue
        wear = _extract_wear(desc.get("tags", []))
        items.append((name, wear))
    return items
