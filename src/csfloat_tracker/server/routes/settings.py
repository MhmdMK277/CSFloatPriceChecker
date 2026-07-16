"""App status, API key management, item database refresh, preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ... import __version__
from ...core import secrets
from ..deps import AppContext, get_ctx

router = APIRouter()


class ApiKeyBody(BaseModel):
    key: str = Field(..., min_length=8, max_length=200)


class PreferencesBody(BaseModel):
    discord_webhook_url: str | None = Field(None, max_length=400)
    desktop_notifications: bool | None = None
    theme: str | None = Field(None, pattern="^(dark|light)$")


@router.get("/status")
async def status(ctx: AppContext = Depends(get_ctx)):
    """One-call app health: key, item DB, rate limits, live clients."""
    return {
        "version": __version__,
        "api_key_set": bool(ctx.client.api_key),
        "api_key_storage": secrets.storage_backend(),
        "itemdb": ctx.itemdb.stats(),
        "rate": ctx.client.rate_status(),
        "ws_clients": ctx.ws.client_count,
    }


@router.post("/settings/api-key")
async def set_api_key(body: ApiKeyBody, ctx: AppContext = Depends(get_ctx)):
    """Validate the key against CSFloat, then store it in the keychain."""
    previous = ctx.client.api_key
    ctx.client.api_key = body.key.strip()
    try:
        profile = await ctx.client.validate_key()
    except Exception:
        ctx.client.api_key = previous
        raise
    backend = secrets.set_api_key(body.key.strip())
    return {"ok": True, "stored_in": backend, "profile": profile}


@router.delete("/settings/api-key")
async def delete_api_key(ctx: AppContext = Depends(get_ctx)):
    secrets.delete_api_key()
    ctx.client.api_key = None
    return {"ok": True}


@router.get("/settings/preferences")
async def get_preferences(ctx: AppContext = Depends(get_ctx)):
    return await ctx.storage.get_setting("preferences", {})


@router.put("/settings/preferences")
async def set_preferences(body: PreferencesBody, ctx: AppContext = Depends(get_ctx)):
    current = await ctx.storage.get_setting("preferences", {})
    current.update(body.model_dump(exclude_none=True))
    await ctx.storage.set_setting("preferences", current)
    return current


@router.post("/itemdb/refresh")
async def refresh_itemdb(ctx: AppContext = Depends(get_ctx)):
    """Force a fresh pull of the CSFloat schema."""
    return await ctx.itemdb.refresh(ctx.client)
