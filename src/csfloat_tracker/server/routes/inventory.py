"""Steam inventory import and valuation.

Valuation uses CSFloat's own reference prices from the item database, so a
full inventory prices instantly without spending any listings-API budget.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...core.inventory import fetch_steam_inventory, parse_inventory
from ...core.schema_parser import expand_image
from ..deps import AppContext, get_ctx

router = APIRouter()

STEAM_ICON_PREFIX = "https://community.akamai.steamstatic.com/economy/image/"


class InventoryUpload(BaseModel):
    data: dict  # raw Steam inventory JSON (assets + descriptions)


def _value_inventory(items, ctx: AppContext) -> dict:
    rows = []
    total_cents = 0
    priced = 0
    by_type: dict[str, int] = {}
    for inv in items:
        variant = ctx.itemdb.lookup(inv.market_hash_name)
        ref = variant.reference_price_cents if variant else None
        line_value = (ref or 0) * inv.quantity
        total_cents += line_value
        if ref:
            priced += 1
        type_key = variant.item_type if variant else "unknown"
        by_type[type_key] = by_type.get(type_key, 0) + line_value
        rows.append({
            "market_hash_name": inv.market_hash_name,
            "quantity": inv.quantity,
            "wear": inv.wear,
            "item_type": type_key,
            "rarity": variant.rarity if variant else None,
            "rarity_name": ctx.itemdb.rarities.get(variant.rarity) if variant and variant.rarity is not None else None,
            "image": expand_image(variant.image) if variant and variant.image else (
                STEAM_ICON_PREFIX + inv.icon_url if inv.icon_url else None
            ),
            "reference_price_cents": ref,
            "line_value_cents": line_value if ref else None,
            "marketable": inv.marketable,
        })
    rows.sort(key=lambda r: -(r["line_value_cents"] or 0))
    return {
        "items": rows,
        "total_value_cents": total_cents,
        "item_count": sum(i.quantity for i in items),
        "priced_count": priced,
        "unpriced_count": len(items) - priced,
        "value_by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "pricing_source": "csfloat_reference",
    }


@router.post("/inventory/upload")
async def upload_inventory(body: InventoryUpload, ctx: AppContext = Depends(get_ctx)):
    """Value an inventory from an uploaded Steam JSON dump."""
    items = parse_inventory(body.data)
    return _value_inventory(items, ctx)


@router.get("/inventory/steam/{steam_id}")
async def fetch_inventory(steam_id: str, ctx: AppContext = Depends(get_ctx)):
    """Fetch and value a public Steam inventory by SteamID64."""
    data = await fetch_steam_inventory(steam_id)
    items = parse_inventory(data)
    return _value_inventory(items, ctx)
