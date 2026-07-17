import httpx
import pytest
import respx

from csfloat_tracker.core.errors import UpstreamError
from csfloat_tracker.core.skinport import ITEMS_URL, fetch_skinport_items

FEED = [
    {"market_hash_name": "AK-47 | Redline (Field-Tested)", "min_price": 27.5, "quantity": 41},
    {"market_hash_name": "Unlisted Item", "min_price": None, "quantity": 0},
    {"market_hash_name": "AWP | Asiimov (Field-Tested)", "min_price": 118.0, "quantity": 12},
]


@respx.mock
async def test_fetch_skinport_items():
    route = respx.get(ITEMS_URL).mock(return_value=httpx.Response(200, json=FEED))
    rows = await fetch_skinport_items()
    assert route.calls[0].request.headers["accept-encoding"] == "br"
    assert "currency=USD" in str(route.calls[0].request.url)
    # Unpriced items are dropped; prices land as cents
    assert len(rows) == 2
    assert rows[0]["min_price_cents"] == 2750
    assert rows[1]["min_price_cents"] == 11800


@respx.mock
async def test_fetch_skinport_406_is_actionable():
    respx.get(ITEMS_URL).mock(return_value=httpx.Response(406))
    with pytest.raises(UpstreamError) as exc:
        await fetch_skinport_items()
    assert "brotli" in exc.value.message.lower()


async def test_skinport_cache_roundtrip(tmp_path):
    from csfloat_tracker.core.storage import Storage

    store = Storage(tmp_path / "sp.db")
    await store.open()
    try:
        await store.replace_skinport_prices([
            {"market_hash_name": "A", "min_price_cents": 100, "quantity": 3, "updated_at": "t1"},
        ])
        await store.replace_skinport_prices([
            {"market_hash_name": "A", "min_price_cents": 90, "quantity": 2, "updated_at": "t2"},
            {"market_hash_name": "B", "min_price_cents": 500, "quantity": 1, "updated_at": "t2"},
        ])
        row = await store.get_skinport_price("A")
        assert row["min_price_cents"] == 90  # replaced, not appended
        status = await store.skinport_status()
        assert status["items"] == 2
        assert await store.get_skinport_price("missing") is None
    finally:
        await store.close()
