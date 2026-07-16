import httpx
import pytest
import respx

from csfloat_tracker.core.errors import NotFoundError
from csfloat_tracker.core.inventory import fetch_steam_inventory, parse_inventory

SAMPLE = {
    "assets": [
        {"classid": "c1", "instanceid": "i1"},
        {"classid": "c1", "instanceid": "i1"},  # duplicate -> quantity 2
        {"classid": "c2", "instanceid": "i2"},
        {"classid": "c3", "instanceid": "i3"},
        {"classid": "unknown", "instanceid": "x"},  # no description -> skipped
    ],
    "descriptions": [
        {
            "classid": "c1", "instanceid": "i1",
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "type": "Classified Rifle", "marketable": 1,
            "tags": [{"category": "Exterior", "localized_tag_name": "Field-Tested"}],
        },
        {
            "classid": "c2", "instanceid": "i2",
            "market_hash_name": "5 Year Veteran Coin",
            "type": "Extraordinary Collectible Coin", "marketable": 0,
            "tags": [],
        },
        {
            "classid": "c3", "instanceid": "i3",
            "market_hash_name": "Dreams & Nightmares Case",
            "type": "Base Grade Container", "marketable": 1,
            "tags": [],
        },
    ],
}


def test_parse_inventory():
    items = parse_inventory(SAMPLE)
    by_name = {i.market_hash_name: i for i in items}
    assert "AK-47 | Redline (Field-Tested)" in by_name
    assert by_name["AK-47 | Redline (Field-Tested)"].quantity == 2
    assert by_name["AK-47 | Redline (Field-Tested)"].wear == "FT"
    assert "Dreams & Nightmares Case" in by_name
    # Coins are ignored
    assert "5 Year Veteran Coin" not in by_name


def test_parse_empty():
    assert parse_inventory({}) == []


@respx.mock
async def test_fetch_steam_inventory_pagination():
    url = "https://steamcommunity.com/inventory/765611/730/2"
    route = respx.get(url)
    route.side_effect = [
        httpx.Response(200, json={
            "assets": SAMPLE["assets"][:2], "descriptions": SAMPLE["descriptions"][:1],
            "more_items": 1, "last_assetid": "42",
        }),
        httpx.Response(200, json={
            "assets": SAMPLE["assets"][2:4], "descriptions": SAMPLE["descriptions"][1:],
        }),
    ]
    data = await fetch_steam_inventory("765611")
    assert route.call_count == 2
    assert "start_assetid=42" in str(route.calls[1].request.url)
    assert len(data["assets"]) == 4


@respx.mock
async def test_fetch_private_inventory():
    respx.get("https://steamcommunity.com/inventory/1/730/2").mock(
        return_value=httpx.Response(403)
    )
    with pytest.raises(NotFoundError):
        await fetch_steam_inventory("1")
