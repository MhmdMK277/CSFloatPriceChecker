"""Background worker behavior: tracking snapshots, alerts, deal scanning."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from csfloat_tracker.core.client import BASE_URL, CSFloatClient
from csfloat_tracker.core.itemdb import ItemDatabase
from csfloat_tracker.core.ratelimit import RateLimiter
from csfloat_tracker.core.schema_parser import parse_schema
from csfloat_tracker.core.storage import Storage
from csfloat_tracker.server.deps import AppContext
from csfloat_tracker.server.worker import Worker

from .conftest import make_listing


@pytest.fixture
async def ctx(tmp_path, mini_schema) -> AppContext:
    storage = Storage(tmp_path / "worker.db")
    await storage.open()
    itemdb = ItemDatabase(tmp_path / "items.json")
    itemdb.items = parse_schema(mini_schema)
    itemdb.generated_at = datetime.now(UTC)
    itemdb._build_index()
    client = CSFloatClient(api_key="k", limiter=RateLimiter(max_wait=1.0), max_retries=0)
    context = AppContext(storage=storage, itemdb=itemdb, client=client)
    yield context
    await context.close()


@respx.mock
async def test_tracking_snapshot(ctx):
    respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(200, json={"data": [make_listing(price=2894)]})
    )
    await ctx.storage.add_tracked_item("AK-47 | Redline (Field-Tested)", {}, 900)
    worker = Worker(ctx)
    await worker.tick()

    snaps = await ctx.storage.get_snapshots("AK-47 | Redline (Field-Tested)")
    assert len(snaps) == 1
    assert snaps[0]["min_price_cents"] == 2894

    # Second tick within the interval must not add another snapshot
    await worker.tick()
    assert len(await ctx.storage.get_snapshots("AK-47 | Redline (Field-Tested)")) == 1


@respx.mock
async def test_alert_fires_once_per_listing(ctx):
    respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(200, json={"data": [
            make_listing(listing_id="A", price=2000, float_value=0.15),
            make_listing(listing_id="B", price=2600, float_value=0.15),  # above max price
        ]})
    )
    await ctx.storage.create_alert(
        "AK-47 | Redline (Field-Tested)", {"max_price_cents": 2500}
    )
    worker = Worker(ctx)
    await worker._check_alerts()
    events = await ctx.storage.list_alert_events()
    assert len(events) == 1
    assert events[0]["listing_id"] == "A"

    # Re-running does not duplicate the event
    await worker._check_alerts()
    assert len(await ctx.storage.list_alert_events()) == 1


@respx.mock
async def test_alert_float_rule(ctx):
    respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(200, json={"data": [
            make_listing(listing_id="LOW", price=5000, float_value=0.005),
            make_listing(listing_id="HIGH", price=5000, float_value=0.5),
        ]})
    )
    await ctx.storage.create_alert(
        "AK-47 | Redline (Field-Tested)", {"max_float": 0.01}
    )
    worker = Worker(ctx)
    await worker._check_alerts()
    events = await ctx.storage.list_alert_events()
    assert [e["listing_id"] for e in events] == ["LOW"]


@respx.mock
async def test_deal_scan(ctx):
    # reference.base_price = 3100 in make_listing; price 2000 => 35.5% discount
    respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(200, json={"data": [
            make_listing(listing_id="DEAL", price=2000),
            make_listing(listing_id="FAIR", price=3050),
        ]})
    )
    worker = Worker(ctx)
    await worker._scan_deals({"min_discount_pct": 15.0, "min_price_cents": 500})
    deals = await ctx.storage.list_deals()
    assert len(deals) == 1
    assert deals[0]["listing_id"] == "DEAL"
    assert deals[0]["discount_pct"] > 30

    # duplicate listings are not re-recorded
    await worker._scan_deals({"min_discount_pct": 15.0, "min_price_cents": 500})
    assert len(await ctx.storage.list_deals()) == 1


async def test_tick_without_key_is_noop(ctx):
    ctx.client.api_key = None
    worker = Worker(ctx)
    await worker.tick()  # must not raise or call the network
