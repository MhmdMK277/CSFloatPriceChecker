import pytest

from csfloat_tracker.core.storage import Storage


@pytest.fixture
async def store(tmp_path):
    s = Storage(tmp_path / "test.db")
    await s.open()
    yield s
    await s.close()


async def test_settings_roundtrip(store):
    assert await store.get_setting("theme") is None
    assert await store.get_setting("theme", "dark") == "dark"
    await store.set_setting("theme", "light")
    assert await store.get_setting("theme") == "light"
    await store.set_setting("nested", {"a": [1, 2]})
    assert (await store.all_settings())["nested"] == {"a": [1, 2]}


async def test_snapshots(store):
    for price in (1000, 1100, 900):
        await store.add_snapshot(
            "AK-47 | Redline (Field-Tested)",
            min_price_cents=price, avg_price_cents=price + 100,
            median_price_cents=price + 50, listing_count=40, min_float=0.16,
        )
    rows = await store.get_snapshots("AK-47 | Redline (Field-Tested)")
    assert len(rows) == 3
    assert rows[0]["min_price_cents"] == 1000
    assert await store.tracked_names_with_history() == ["AK-47 | Redline (Field-Tested)"]


async def test_watchlist_crud(store):
    wl = await store.create_watchlist("Dream Loadout")
    await store.add_watchlist_item(wl["id"], "AK-47 | Redline (Field-Tested)", {"wear": "FT"})
    await store.add_watchlist_item(wl["id"], "AWP | Asiimov (Field-Tested)")
    # duplicate is ignored
    await store.add_watchlist_item(wl["id"], "AWP | Asiimov (Field-Tested)")

    detail = await store.get_watchlist(wl["id"])
    assert len(detail["items"]) == 2
    assert detail["items"][0]["filters"] == {"wear": "FT"}

    item_id = detail["items"][0]["id"]
    await store.update_watchlist_item_price(item_id, 2894)
    await store.update_watchlist_item_price(item_id, 3000)
    detail = await store.get_watchlist(wl["id"])
    updated = next(i for i in detail["items"] if i["id"] == item_id)
    assert updated["last_price_cents"] == 3000
    assert updated["prev_price_cents"] == 2894

    lists = await store.list_watchlists()
    assert lists[0]["item_count"] == 2

    await store.remove_watchlist_item(wl["id"], item_id)
    await store.delete_watchlist(wl["id"])
    assert await store.get_watchlist(wl["id"]) is None


async def test_tracked_items(store):
    await store.add_tracked_item("X", {"wear": "FN"}, interval_seconds=300)
    await store.add_tracked_item("X", interval_seconds=600)  # upsert
    items = await store.list_tracked_items()
    assert len(items) == 1
    assert items[0]["interval_seconds"] == 600

    await store.set_tracked_item_active(items[0]["id"], False)
    assert await store.list_tracked_items(active_only=True) == []
    await store.delete_tracked_item(items[0]["id"])
    assert await store.list_tracked_items() == []


async def test_alerts_and_events(store):
    alert = await store.create_alert("AWP | Fade (Factory New)", {"max_price_cents": 100000})
    alerts = await store.list_alerts()
    assert alerts[0]["rule"] == {"max_price_cents": 100000}

    await store.record_alert_event(
        alert["id"], listing_id="L1", price_cents=95000, float_value=0.01,
        message="AWP | Fade below $1000",
    )
    events = await store.list_alert_events()
    assert events[0]["listing_id"] == "L1"
    assert events[0]["market_hash_name"] == "AWP | Fade (Factory New)"
    assert (await store.list_alerts())[0]["trigger_count"] == 1
    assert await store.latest_alert_event_listing_ids(alert["id"]) == {"L1"}

    await store.set_alert_active(alert["id"], False)
    assert await store.list_alerts(active_only=True) == []
    await store.delete_alert(alert["id"])


async def test_deals_dedupe(store):
    kwargs = dict(
        market_hash_name="M4A4 | Howl (Field-Tested)", price_cents=300000,
        reference_price_cents=400000, discount_pct=25.0, float_value=0.2,
        listing_url="https://csfloat.com/item/1",
    )
    assert await store.record_deal(listing_id="1", **kwargs) is True
    assert await store.record_deal(listing_id="1", **kwargs) is False  # duplicate
    assert len(await store.list_deals()) == 1


async def test_portfolio(store):
    await store.add_portfolio_entry("AK-47 | Case Hardened (Field-Tested)", 5000, quantity=2)
    rows = await store.list_portfolio()
    assert rows[0]["quantity"] == 2
    await store.delete_portfolio_entry(rows[0]["id"])
    assert await store.list_portfolio() == []
