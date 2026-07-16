import httpx
import pytest
import respx

from csfloat_tracker.core.client import BASE_URL, CSFloatClient
from csfloat_tracker.core.errors import AuthError, NotFoundError, RateLimitError
from csfloat_tracker.core.ratelimit import RateLimiter

from .conftest import make_listing


@pytest.fixture
def client():
    return CSFloatClient(api_key="test-key", limiter=RateLimiter(max_wait=3.0))


@respx.mock
async def test_get_listings_parses(client):
    route = respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [make_listing()], "cursor": "abc"},
            headers={"x-ratelimit-limit": "100", "x-ratelimit-remaining": "99"},
        )
    )
    page = await client.get_listings(market_hash_name="AK-47 | Redline (Field-Tested)")
    assert route.called
    sent = route.calls[0].request
    assert sent.headers["authorization"] == "test-key"
    assert page.cursor == "abc"
    listing = page.listings[0]
    assert listing.price_cents == 2894
    assert listing.price_usd == 28.94
    assert listing.float_value == 0.23
    assert listing.url == "https://csfloat.com/item/123456"
    assert listing.seller.username == "trader1"
    assert listing.stickers[0].name == "Sticker | Shooter"
    assert listing.reference_price_cents == 3100
    await client.close()


@respx.mock
async def test_get_listings_bare_list(client):
    respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(200, json=[make_listing()])
    )
    page = await client.get_listings()
    assert len(page.listings) == 1
    assert page.cursor is None
    await client.close()


@respx.mock
async def test_auth_error(client):
    respx.get(f"{BASE_URL}/me").mock(return_value=httpx.Response(401, json={}))
    with pytest.raises(AuthError):
        await client.get_me()
    await client.close()


@respx.mock
async def test_not_found(client):
    respx.get(f"{BASE_URL}/listings/nope").mock(return_value=httpx.Response(404, json={}))
    with pytest.raises(NotFoundError):
        await client.get_listing("nope")
    await client.close()


@respx.mock
async def test_429_retries_then_succeeds(client):
    route = respx.get(f"{BASE_URL}/listings")
    route.side_effect = [
        httpx.Response(429, headers={"retry-after": "0"}),
        httpx.Response(200, json={"data": [make_listing()]}),
    ]
    page = await client.get_listings()
    assert len(page.listings) == 1
    assert route.call_count == 2
    await client.close()


@respx.mock
async def test_429_gives_up_with_rate_limit_error():
    client = CSFloatClient(api_key="k", limiter=RateLimiter(max_wait=0.01), max_retries=1)
    respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(429, headers={"retry-after": "60"})
    )
    with pytest.raises(RateLimitError) as exc:
        await client.get_listings()
    assert exc.value.retry_after >= 1
    await client.close()


@respx.mock
async def test_5xx_retries(client):
    route = respx.get(f"{BASE_URL}/listings")
    route.side_effect = [
        httpx.Response(502),
        httpx.Response(200, json={"data": []}),
    ]
    page = await client.get_listings()
    assert page.listings == []
    assert route.call_count == 2
    await client.close()


@respx.mock
async def test_schema_is_cached(client):
    route = respx.get(f"{BASE_URL}/schema").mock(
        return_value=httpx.Response(200, json={"weapons": {}})
    )
    await client.get_schema()
    await client.get_schema()
    assert route.call_count == 1  # second hit served from cache
    await client.close()


@respx.mock
async def test_rate_status_tracks_headers(client):
    respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(
            200,
            json={"data": []},
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "42",
                "x-ratelimit-reset": "30",
            },
        )
    )
    await client.get_listings()
    status = client.rate_status()
    assert status["listings"]["limit"] == 100
    assert status["listings"]["remaining"] == 42
    assert 0 < status["listings"]["resets_in_seconds"] <= 30
    await client.close()


@respx.mock
async def test_unknown_filters_dropped(client):
    route = respx.get(f"{BASE_URL}/listings").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    await client.get_listings(market_hash_name="X", bogus_param="y", min_float=0.1)
    url = str(route.calls[0].request.url)
    assert "bogus_param" not in url
    assert "min_float=0.1" in url
    await client.close()
