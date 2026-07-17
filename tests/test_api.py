"""Integration tests for the REST API using an in-process ASGI transport."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from csfloat_tracker.core.client import BASE_URL, CSFloatClient
from csfloat_tracker.core.itemdb import ItemDatabase
from csfloat_tracker.core.ratelimit import RateLimiter
from csfloat_tracker.core.schema_parser import collections_map, parse_schema, rarities_map
from csfloat_tracker.core.storage import Storage
from csfloat_tracker.server.app import create_app
from csfloat_tracker.server.deps import AppContext

from .conftest import make_listing


@pytest.fixture
async def ctx(tmp_path, mini_schema) -> AppContext:
    storage = Storage(tmp_path / "api.db")
    await storage.open()
    itemdb = ItemDatabase(tmp_path / "items.json")
    itemdb.items = parse_schema(mini_schema)
    itemdb.collections = collections_map(mini_schema)
    itemdb.rarities = rarities_map(mini_schema)
    itemdb.generated_at = datetime.now(UTC)
    itemdb._build_index()
    client = CSFloatClient(api_key="test-key", limiter=RateLimiter(max_wait=1.0), max_retries=0)
    context = AppContext(storage=storage, itemdb=itemdb, client=client)
    yield context
    await context.close()


@pytest.fixture
async def api(ctx):
    app = create_app(ctx=ctx, start_worker=False)
    app.state.ctx = ctx  # lifespan does not run under ASGITransport
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_status(api):
    r = await api.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["api_key_set"] is True
    assert body["itemdb"]["market_names"] > 10


async def test_search(api):
    r = await api.get("/api/search", params={"q": "redline"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert any("Redline" in x["market_hash_name"] for x in results)
    first = results[0]
    assert first["image"] is None or first["image"].startswith("https://")


async def test_item_detail(api):
    r = await api.get("/api/items/detail", params={"name": "AK-47 | Redline (Field-Tested)"})
    assert r.status_code == 200
    body = r.json()
    assert body["reference_price_cents"] == 2894
    assert body["collection_names"] == ["The Test Collection"]

    r = await api.get("/api/items/detail", params={"name": "Nope"})
    assert r.status_code == 404


@respx.mock
async def test_listings_proxy(api):
    respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(200, json={"data": [make_listing()], "cursor": "next"})
    )
    r = await api.get("/api/listings", params={
        "name": "AK-47 | Redline (Field-Tested)", "wear": "FT", "category": "normal",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["cursor"] == "next"
    assert body["listings"][0]["price_usd"] == 28.94
    # Listing carries its own reference (3100): discount = 1 - 2894/3100
    assert body["listings"][0]["discount_pct"] == pytest.approx(6.65, abs=0.1)
    assert body["summary"]["listing_count"] == 1


@respx.mock
async def test_listings_rate_limit_maps_to_429(api):
    respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(429, headers={"retry-after": "120"})
    )
    r = await api.get("/api/listings", params={"name": "X"})
    assert r.status_code == 429
    assert "rate limit" in r.json()["error"].lower()


async def test_watchlist_flow(api):
    r = await api.post("/api/watchlists", json={"name": "Loadout"})
    assert r.status_code == 201
    wid = r.json()["id"]

    r = await api.post(f"/api/watchlists/{wid}/items", json={
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
    })
    assert r.status_code == 201

    with respx.mock:
        respx.get(f"{BASE_URL}/listings").mock(
            return_value=httpx.Response(200, json={"data": [make_listing(price=2700)]})
        )
        r = await api.post(f"/api/watchlists/{wid}/refresh")
    assert r.status_code == 200
    assert r.json()["items"][0]["last_price_cents"] == 2700

    r = await api.get(f"/api/watchlists/{wid}/export", params={"fmt": "csv"})
    assert r.status_code == 200
    assert "AK-47 | Redline" in r.text

    r = await api.delete(f"/api/watchlists/{wid}")
    assert r.status_code == 200
    r = await api.get(f"/api/watchlists/{wid}")
    assert r.status_code == 404


async def test_alerts_crud(api):
    r = await api.post("/api/alerts", json={
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "rule": {"max_price_cents": 2500, "max_float": 0.2},
    })
    assert r.status_code == 201
    alert_id = r.json()["id"]

    r = await api.get("/api/alerts")
    assert r.json()["alerts"][0]["rule"] == {"max_price_cents": 2500, "max_float": 0.2}

    r = await api.patch(f"/api/alerts/{alert_id}", params={"active": "false"})
    assert r.status_code == 200
    r = await api.delete(f"/api/alerts/{alert_id}")
    assert r.status_code == 200


async def test_tracked_and_history(api, ctx):
    r = await api.post("/api/tracked", json={
        "market_hash_name": "AK-47 | Redline (Field-Tested)", "interval_seconds": 300,
    })
    assert r.status_code == 201

    # invalid interval falls back to default
    r = await api.post("/api/tracked", json={
        "market_hash_name": "X", "interval_seconds": 123,
    })
    assert r.json()["interval_seconds"] == 900

    await ctx.storage.add_snapshot(
        "AK-47 | Redline (Field-Tested)", min_price_cents=2800, avg_price_cents=3000,
        median_price_cents=2950, listing_count=42, min_float=0.16,
    )
    r = await api.get("/api/history", params={"name": "AK-47 | Redline (Field-Tested)"})
    body = r.json()
    assert body["summary"]["latest_cents"] == 2800
    assert len(body["snapshots"]) == 1

    r = await api.get("/api/tracked")
    ids = [t["id"] for t in r.json()["tracked"]]
    for tid in ids:
        await api.delete(f"/api/tracked/{tid}")


def _steam_payload(context: str, asset_ids: list[str]) -> dict:
    return {
        "assets": [
            {"appid": 730, "contextid": context, "assetid": a, "classid": f"c{a}", "instanceid": "0"}
            for a in asset_ids
        ],
        "descriptions": [
            {"classid": f"c{a}", "instanceid": "0",
             "market_hash_name": "AK-47 | Redline (Field-Tested)",
             "type": "Classified Rifle", "marketable": 1,
             "tags": [{"category": "Exterior", "localized_tag_name": "Field-Tested"}]}
            for a in asset_ids
        ],
    }


async def test_inventory_upload(api):
    r = await api.post("/api/inventory/upload", json={"data": {
        "assets": [{"classid": "c1", "instanceid": "i1"}],
        "descriptions": [{
            "classid": "c1", "instanceid": "i1",
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "type": "Classified Rifle", "marketable": 1,
            "tags": [{"category": "Exterior", "localized_tag_name": "Field-Tested"}],
        }],
    }})
    assert r.status_code == 200
    body = r.json()
    assert body["total_value_cents"] == 2894
    assert body["priced_count"] == 1
    assert body["truncated"] is False
    assert body["items"][0]["rarity_name"] is None or isinstance(body["items"][0]["rarity_name"], str)


async def test_inventory_steam_vanity_soft_error(api):
    r = await api.get("/api/inventory/steam", params={"q": "https://steamcommunity.com/id/sparkles"})
    assert r.status_code == 200
    body = r.json()
    assert body["steam_id"] is None
    assert "sparkles" in body["error"]
    assert body["inventory"] is None


@respx.mock
async def test_inventory_steam_rate_limited_returns_steam_id(api):
    sid = "76561198349712477"
    respx.get(f"https://steamcommunity.com/inventory/{sid}/730/2").mock(
        return_value=httpx.Response(429)
    )
    r = await api.get("/api/inventory/steam", params={
        "q": f"https://steamcommunity.com/profiles/{sid}/",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["steam_id"] == sid  # UI needs this to build manual-load links
    assert "Manual Load" in body["error"]
    assert body["inventory"] is None


@respx.mock
async def test_inventory_steam_success_merges_contexts(api):
    sid = "76561198349712477"
    respx.get(f"https://steamcommunity.com/inventory/{sid}/730/2").mock(
        return_value=httpx.Response(200, json=_steam_payload("2", ["1", "2"]))
    )
    respx.get(f"https://steamcommunity.com/inventory/{sid}/730/16").mock(
        return_value=httpx.Response(200, json=_steam_payload("16", ["9"]))
    )
    r = await api.get("/api/inventory/steam", params={"q": sid})
    body = r.json()
    assert body["error"] is None
    inv = body["inventory"]
    assert inv["item_count"] == 3
    assert inv["context_counts"] == {"tradable": 2, "trade_protected": 1, "other": 0}


async def test_inventory_manual_merges_and_counts(api):
    r = await api.post("/api/inventory/manual", json={
        "tradable": _steam_payload("2", ["1", "2"]),
        "trade_protected": _steam_payload("16", ["9"]),
    })
    assert r.status_code == 200
    body = r.json()
    assert body["item_count"] == 3
    assert body["context_counts"]["trade_protected"] == 1
    assert body["total_value_cents"] == 2894 * 3


async def test_inventory_manual_single_context(api):
    r = await api.post("/api/inventory/manual", json={
        "trade_protected": _steam_payload("16", ["9"]),
    })
    assert r.status_code == 200
    assert r.json()["item_count"] == 1


async def test_inventory_manual_rejects_empty(api):
    r = await api.post("/api/inventory/manual", json={})
    assert r.status_code == 400
    assert "Paste" in r.json()["error"]

    r = await api.post("/api/inventory/manual", json={"tradable": {"assets": []}})
    assert r.status_code == 400
    assert "no items" in r.json()["error"]


async def test_portfolio_flow(api):
    r = await api.post("/api/portfolio", json={
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "buy_price_cents": 2000, "quantity": 2,
    })
    assert r.status_code == 201
    r = await api.get("/api/portfolio")
    body = r.json()
    assert body["total_cost_cents"] == 4000
    assert body["total_value_cents"] == 2894 * 2
    entry_id = body["entries"][0]["id"]
    r = await api.delete(f"/api/portfolio/{entry_id}")
    assert r.status_code == 200


async def test_deals_config(api):
    r = await api.get("/api/deals/config")
    assert r.json()["enabled"] is False
    r = await api.put("/api/deals/config", json={
        "enabled": True, "min_discount_pct": 20, "min_price_cents": 1000,
        "interval_seconds": 300,
    })
    assert r.json()["enabled"] is True
    r = await api.get("/api/deals/config")
    assert r.json()["min_discount_pct"] == 20
    r = await api.get("/api/deals")
    assert r.json()["deals"] == []


@respx.mock
async def test_api_key_set_and_validate(api, ctx, monkeypatch):
    import csfloat_tracker.core.secrets as secrets_mod

    monkeypatch.setattr(secrets_mod, "_keyring", lambda: None)
    respx.get(f"{BASE_URL}/me").mock(
        return_value=httpx.Response(200, json={"user": {"username": "tester", "steam_id": "7656"}})
    )
    r = await api.post("/api/settings/api-key", json={"key": "new-valid-key"})
    assert r.status_code == 200
    assert r.json()["profile"]["username"] == "tester"
    assert ctx.client.api_key == "new-valid-key"

    r = await api.delete("/api/settings/api-key")
    assert r.status_code == 200
    assert ctx.client.api_key is None


@respx.mock
async def test_api_key_invalid_is_rolled_back(api, ctx):
    respx.get(f"{BASE_URL}/me").mock(return_value=httpx.Response(401))
    r = await api.post("/api/settings/api-key", json={"key": "bad-key-value"})
    assert r.status_code == 401
    assert ctx.client.api_key == "test-key"  # rolled back


@respx.mock
async def test_itemdb_refresh_endpoint(api, mini_schema):
    respx.get(f"{BASE_URL}/schema").mock(return_value=httpx.Response(200, json=mini_schema))
    r = await api.post("/api/itemdb/refresh")
    assert r.status_code == 200
    assert r.json()["base_items"] > 0


async def test_preferences(api):
    r = await api.put("/api/settings/preferences", json={"theme": "light"})
    assert r.json()["theme"] == "light"
    r = await api.get("/api/settings/preferences")
    assert r.json() == {"theme": "light"}
