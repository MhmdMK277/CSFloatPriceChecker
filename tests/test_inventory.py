import httpx
import pytest
import respx

from csfloat_tracker.core.errors import NotFoundError
from csfloat_tracker.core.inventory import (
    context_counts,
    fetch_full_inventory,
    fetch_steam_inventory,
    merge_inventory_payloads,
    parse_inventory,
    parse_steam_input,
)

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


# ----------------------------------------------------------------------
# Steam input parsing
# ----------------------------------------------------------------------

STEAM_ID = "76561198349712477"


@pytest.mark.parametrize("value", [
    STEAM_ID,
    f"  {STEAM_ID}  ",
    f"https://steamcommunity.com/profiles/{STEAM_ID}",
    f"https://steamcommunity.com/profiles/{STEAM_ID}/",
    f"http://steamcommunity.com/profiles/{STEAM_ID}/inventory/",
    f"steamcommunity.com/profiles/{STEAM_ID}",
])
def test_parse_steam_input_valid(value):
    steam_id, error = parse_steam_input(value)
    assert steam_id == STEAM_ID
    assert error is None


def test_parse_steam_input_vanity():
    steam_id, error = parse_steam_input("https://steamcommunity.com/id/customname/")
    assert steam_id is None
    assert "customname" in error
    assert "steamid.io" in error


@pytest.mark.parametrize("value", ["", "hello", "1234", "https://example.com/profiles/x"])
def test_parse_steam_input_invalid(value):
    steam_id, error = parse_steam_input(value)
    assert steam_id is None
    assert error


# ----------------------------------------------------------------------
# Payload merging (contexts 2 + 16)
# ----------------------------------------------------------------------

def _payload(context: str, asset_ids: list[str], more: bool = False, total: int | None = None):
    p = {
        "assets": [
            {"appid": 730, "contextid": context, "assetid": a, "classid": f"c{a}", "instanceid": "0"}
            for a in asset_ids
        ],
        "descriptions": [
            {"classid": f"c{a}", "instanceid": "0", "market_hash_name": f"Item {a}",
             "type": "Rifle", "marketable": 1, "tags": []}
            for a in asset_ids
        ],
    }
    if more:
        p["more_items"] = 1
    if total is not None:
        p["total_inventory_count"] = total
    return p


def test_merge_contexts_and_dedupe():
    tradable = _payload("2", ["1", "2", "3"])
    protected = _payload("16", ["10", "11"])
    duplicate = _payload("2", ["2"])  # same asset pasted twice

    merged = merge_inventory_payloads([tradable, protected, duplicate])
    assert len(merged["assets"]) == 5
    assert merged["truncated"] is False
    assert context_counts(merged) == {"tradable": 3, "trade_protected": 2, "other": 0}

    items = parse_inventory(merged)
    assert len(items) == 5


def test_merge_flags_truncation():
    assert merge_inventory_payloads([_payload("2", ["1"], more=True)])["truncated"] is True
    assert merge_inventory_payloads([_payload("2", ["1"], total=500)])["truncated"] is True
    assert merge_inventory_payloads([_payload("2", ["1"], total=1)])["truncated"] is False


@respx.mock
async def test_fetch_full_inventory_protected_best_effort():
    respx.get(f"https://steamcommunity.com/inventory/{STEAM_ID}/730/2").mock(
        return_value=httpx.Response(200, json=_payload("2", ["1", "2"]))
    )
    # Trade-protected context rate-limited: must not break the whole fetch
    respx.get(f"https://steamcommunity.com/inventory/{STEAM_ID}/730/16").mock(
        return_value=httpx.Response(429)
    )
    merged = await fetch_full_inventory(STEAM_ID)
    assert context_counts(merged)["tradable"] == 2
    assert context_counts(merged)["trade_protected"] == 0


@respx.mock
async def test_fetch_full_inventory_both_contexts():
    respx.get(f"https://steamcommunity.com/inventory/{STEAM_ID}/730/2").mock(
        return_value=httpx.Response(200, json=_payload("2", ["1"]))
    )
    respx.get(f"https://steamcommunity.com/inventory/{STEAM_ID}/730/16").mock(
        return_value=httpx.Response(200, json=_payload("16", ["9"]))
    )
    merged = await fetch_full_inventory(STEAM_ID)
    assert len(merged["assets"]) == 2
