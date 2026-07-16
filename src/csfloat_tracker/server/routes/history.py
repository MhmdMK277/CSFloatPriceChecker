"""Price history snapshots and tracked-item management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ...core.stats import history_summary
from ..deps import AppContext, get_ctx

router = APIRouter()

TRACK_INTERVALS = {60, 300, 900, 3600, 86400}  # 1m / 5m / 15m / 1h / daily


class TrackRequest(BaseModel):
    market_hash_name: str
    interval_seconds: int = Field(900, description="one of 60/300/900/3600/86400")
    filters: dict = Field(default_factory=dict)


@router.get("/history")
async def get_history(
    name: str = Query(...),
    since: str | None = Query(None, description="ISO timestamp lower bound"),
    ctx: AppContext = Depends(get_ctx),
):
    snapshots = await ctx.storage.get_snapshots(name, since=since)
    return {
        "market_hash_name": name,
        "snapshots": snapshots,
        "summary": history_summary(snapshots),
    }


@router.get("/tracked")
async def list_tracked(ctx: AppContext = Depends(get_ctx)):
    return {"tracked": await ctx.storage.list_tracked_items()}


@router.post("/tracked", status_code=201)
async def add_tracked(body: TrackRequest, ctx: AppContext = Depends(get_ctx)):
    interval = body.interval_seconds if body.interval_seconds in TRACK_INTERVALS else 900
    await ctx.storage.add_tracked_item(body.market_hash_name, body.filters, interval)
    return {"ok": True, "interval_seconds": interval}


@router.patch("/tracked/{item_id}")
async def set_tracked_active(
    item_id: int, active: bool = Query(...), ctx: AppContext = Depends(get_ctx)
):
    await ctx.storage.set_tracked_item_active(item_id, active)
    return {"ok": True}


@router.delete("/tracked/{item_id}")
async def delete_tracked(item_id: int, ctx: AppContext = Depends(get_ctx)):
    await ctx.storage.delete_tracked_item(item_id)
    return {"ok": True}
