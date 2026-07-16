"""Alert rules and the alert event log."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..deps import AppContext, get_ctx

router = APIRouter()


class AlertRule(BaseModel):
    """Trigger conditions; any combination must all hold."""

    max_price_cents: int | None = Field(None, ge=0)
    min_float: float | None = Field(None, ge=0, le=1)
    max_float: float | None = Field(None, ge=0, le=1)
    category: str | None = Field(None, pattern="^(normal|stattrak|souvenir)$")
    type: str | None = Field(None, pattern="^(buy_now|auction)$")


class AlertCreate(BaseModel):
    market_hash_name: str
    rule: AlertRule


@router.get("/alerts")
async def list_alerts(ctx: AppContext = Depends(get_ctx)):
    return {"alerts": await ctx.storage.list_alerts()}


@router.post("/alerts", status_code=201)
async def create_alert(body: AlertCreate, ctx: AppContext = Depends(get_ctx)):
    rule = body.rule.model_dump(exclude_none=True)
    return await ctx.storage.create_alert(body.market_hash_name, rule)


@router.patch("/alerts/{alert_id}")
async def set_alert_active(
    alert_id: int, active: bool = Query(...), ctx: AppContext = Depends(get_ctx)
):
    await ctx.storage.set_alert_active(alert_id, active)
    return {"ok": True}


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int, ctx: AppContext = Depends(get_ctx)):
    await ctx.storage.delete_alert(alert_id)
    return {"ok": True}


@router.get("/alerts/events")
async def alert_events(limit: int = Query(100, ge=1, le=500), ctx: AppContext = Depends(get_ctx)):
    return {"events": await ctx.storage.list_alert_events(limit)}
