"""Watchlists (price groups): CRUD, refresh and export."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ...core.errors import CSFloatError
from ..deps import AppContext, get_ctx

router = APIRouter()


class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class WatchlistItemAdd(BaseModel):
    market_hash_name: str
    filters: dict = Field(default_factory=dict)


@router.get("/watchlists")
async def list_watchlists(ctx: AppContext = Depends(get_ctx)):
    return {"watchlists": await ctx.storage.list_watchlists()}


@router.post("/watchlists", status_code=201)
async def create_watchlist(body: WatchlistCreate, ctx: AppContext = Depends(get_ctx)):
    try:
        return await ctx.storage.create_watchlist(body.name)
    except Exception as exc:
        raise HTTPException(409, detail=f"A watchlist named '{body.name}' already exists.") from exc


@router.get("/watchlists/{watchlist_id}")
async def get_watchlist(watchlist_id: int, ctx: AppContext = Depends(get_ctx)):
    wl = await ctx.storage.get_watchlist(watchlist_id)
    if not wl:
        raise HTTPException(404, detail="Watchlist not found.")
    return wl


@router.delete("/watchlists/{watchlist_id}")
async def delete_watchlist(watchlist_id: int, ctx: AppContext = Depends(get_ctx)):
    await ctx.storage.delete_watchlist(watchlist_id)
    return {"ok": True}


@router.post("/watchlists/{watchlist_id}/items", status_code=201)
async def add_item(
    watchlist_id: int, body: WatchlistItemAdd, ctx: AppContext = Depends(get_ctx)
):
    if not await ctx.storage.get_watchlist(watchlist_id):
        raise HTTPException(404, detail="Watchlist not found.")
    await ctx.storage.add_watchlist_item(watchlist_id, body.market_hash_name, body.filters)
    return {"ok": True}


@router.delete("/watchlists/{watchlist_id}/items/{item_id}")
async def remove_item(watchlist_id: int, item_id: int, ctx: AppContext = Depends(get_ctx)):
    await ctx.storage.remove_watchlist_item(watchlist_id, item_id)
    return {"ok": True}


@router.post("/watchlists/{watchlist_id}/refresh")
async def refresh_watchlist(watchlist_id: int, ctx: AppContext = Depends(get_ctx)):
    """Fetch the current lowest price for every item in the watchlist."""
    wl = await ctx.storage.get_watchlist(watchlist_id)
    if not wl:
        raise HTTPException(404, detail="Watchlist not found.")

    errors: list[str] = []
    for item in wl["items"]:
        try:
            page = await ctx.client.get_listings(
                market_hash_name=item["market_hash_name"],
                sort_by="lowest_price",
                limit=1,
                type="buy_now",
                **{k: v for k, v in item["filters"].items() if k in ("min_float", "max_float")},
            )
            price = page.listings[0].price_cents if page.listings else None
            await ctx.storage.update_watchlist_item_price(item["id"], price)
        except CSFloatError as exc:
            errors.append(f"{item['market_hash_name']}: {exc.message}")
            if getattr(exc, "status", None) == 429:
                break  # stop hammering when rate limited

    refreshed = await ctx.storage.get_watchlist(watchlist_id)
    refreshed["errors"] = errors
    return refreshed


@router.get("/watchlists/{watchlist_id}/export")
async def export_watchlist(
    watchlist_id: int, fmt: str = "csv", ctx: AppContext = Depends(get_ctx)
):
    wl = await ctx.storage.get_watchlist(watchlist_id)
    if not wl:
        raise HTTPException(404, detail="Watchlist not found.")
    if fmt == "json":
        return wl
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["market_hash_name", "last_price_usd", "prev_price_usd", "last_checked_at"])
    for item in wl["items"]:
        writer.writerow([
            item["market_hash_name"],
            (item["last_price_cents"] or 0) / 100 if item["last_price_cents"] else "",
            (item["prev_price_cents"] or 0) / 100 if item["prev_price_cents"] else "",
            item["last_checked_at"] or "",
        ])
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{wl["name"]}.csv"'},
    )
