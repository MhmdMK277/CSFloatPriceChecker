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
    steam_id: str | None = None  # attribution for snapshot history, if known


class ManualLoad(BaseModel):
    """Pasted inventory JSON per context; either side may be omitted."""

    tradable: dict | None = None
    trade_protected: dict | None = None
    steam_id: str | None = None


async def _persist_result(
    ctx: AppContext, steam_id: str | None, result: dict, *, method: str
) -> None:
    """Remember the session and record a snapshot for history.

    Falls back to the remembered SteamID so a manual paste or upload that
    arrives without one (user never clicked Fetch this session) still lands
    in that user's history instead of being dropped.
    """
    if not steam_id:
        steam_id = await ctx.storage.get_setting("last_steam_id")
    if steam_id:
        await ctx.storage.set_setting("last_steam_id", steam_id)
        await ctx.storage.save_inventory_snapshot(
            steam_id,
            total_value_cents=result["total_value_cents"],
            item_count=result["item_count"],
            priced_count=result["priced_count"],
            items=result["items"],
            context_counts=result["context_counts"],
            value_by_type=result["value_by_type"],
        )
    await ctx.storage.set_setting("inventory_method", method)


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
        # Remember the id anyway — the UI pre-populates Manual Load with it.
        await ctx.storage.set_setting("last_steam_id", steam_id)
        return {"steam_id": steam_id, "error": exc.message, "inventory": None}
    result = _value_inventory(merged, ctx)
    await _persist_result(ctx, steam_id, result, method="auto")
    return {"steam_id": steam_id, "error": None, "inventory": result}


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
    result = _value_inventory(merged, ctx)
    await _persist_result(ctx, body.steam_id, result, method="manual")
    return result


@router.post("/inventory/upload")
async def upload_inventory(body: InventoryUpload, ctx: AppContext = Depends(get_ctx)):
    """Value an inventory from an uploaded Steam JSON dump."""
    merged = merge_inventory_payloads([body.data])
    result = _value_inventory(merged, ctx)
    await _persist_result(ctx, body.steam_id, result, method="upload")
    return result


@router.get("/inventory/session")
async def inventory_session(ctx: AppContext = Depends(get_ctx)):
    """Everything the inventory page needs on load: remembered id, preferred
    method, and the freshest snapshot for instant display."""
    steam_id = await ctx.storage.get_setting("last_steam_id")
    method = await ctx.storage.get_setting("inventory_method", "auto")
    latest = None
    if steam_id:
        latest = await ctx.storage.get_latest_inventory_snapshot(steam_id)
        if latest:
            # Fill the fields the live-valuation response carries so the UI
            # can render a stored snapshot with the exact same component.
            latest["unpriced_count"] = len(latest["items"]) - latest["priced_count"]
            latest["truncated"] = False
            latest["pricing_source"] = "csfloat_reference"
    return {"steam_id": steam_id, "method": method, "latest": latest}


@router.get("/inventory/history")
async def inventory_history(
    steam_id: str | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
    ctx: AppContext = Depends(get_ctx),
):
    """Snapshot summaries (oldest first) for the value-over-time view."""
    steam_id = steam_id or await ctx.storage.get_setting("last_steam_id")
    if not steam_id:
        return {"steam_id": None, "snapshots": []}
    return {
        "steam_id": steam_id,
        "snapshots": await ctx.storage.list_inventory_snapshots(steam_id, limit),
    }
