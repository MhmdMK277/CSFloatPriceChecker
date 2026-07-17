"""Steam inventory import and valuation.

Three import paths, in order of reliability:
- manual paste of inventory JSON per context (works around Steam's
  aggressive rate limiting — the user copies from their own browser)
- automatic fetch by SteamID64 / profile URL (works sometimes)
- raw JSON dump upload

Valuation uses CSFloat's own reference prices from the item database, so a
full inventory prices instantly without spending any listings-API budget.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...core.errors import CSFloatError
from ...core.inventory import (
    context_counts,
    fetch_full_inventory,
    merge_inventory_payloads,
    parse_inventory,
    parse_steam_input,
)
from ...core.schema_parser import expand_image
from ..deps import AppContext, get_ctx

router = APIRouter()

STEAM_ICON_PREFIX = "https://community.akamai.steamstatic.com/economy/image/"


class InventoryUpload(BaseModel):
    data: dict  # raw Steam inventory JSON (assets + descriptions)


class ManualLoad(BaseModel):
    """Pasted inventory JSON per context; either side may be omitted."""

    tradable: dict | None = None
    trade_protected: dict | None = None


def _value_inventory(merged: dict[str, Any], ctx: AppContext) -> dict:
    items = parse_inventory(merged)
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
        "context_counts": context_counts(merged),
        "truncated": bool(merged.get("truncated")),
        "pricing_source": "csfloat_reference",
    }


@router.get("/inventory/steam")
async def fetch_inventory(
    q: str = Query(..., description="SteamID64 or steamcommunity.com profile URL"),
    ctx: AppContext = Depends(get_ctx),
):
    """Resolve the input and attempt an automatic fetch.

    Always returns 200 with a soft result so the UI can pre-populate the
    Manual Load links even when Steam rate-limits the fetch:
    ``{steam_id, error, inventory}``.
    """
    steam_id, parse_error = parse_steam_input(q)
    if not steam_id:
        return {"steam_id": None, "error": parse_error, "inventory": None}
    try:
        merged = await fetch_full_inventory(steam_id)
    except CSFloatError as exc:
        return {"steam_id": steam_id, "error": exc.message, "inventory": None}
    return {"steam_id": steam_id, "error": None, "inventory": _value_inventory(merged, ctx)}


@router.post("/inventory/manual")
async def manual_load(body: ManualLoad, ctx: AppContext = Depends(get_ctx)):
    """Value inventory JSON the user pasted from their own browser session."""
    payloads = [p for p in (body.tradable, body.trade_protected) if p]
    if not payloads:
        raise CSFloatError("Paste at least one inventory JSON response.", status=400)
    merged = merge_inventory_payloads(payloads)
    if not merged["assets"]:
        raise CSFloatError(
            "That JSON has no items — make sure you copied the full response body.",
            status=400,
        )
    return _value_inventory(merged, ctx)


@router.post("/inventory/upload")
async def upload_inventory(body: InventoryUpload, ctx: AppContext = Depends(get_ctx)):
    """Value an inventory from an uploaded Steam JSON dump."""
    merged = merge_inventory_payloads([body.data])
    return _value_inventory(merged, ctx)
