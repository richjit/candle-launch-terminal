# backend/tests/test_coingecko.py
import pytest
import httpx
from app.cache import MemoryCache
from app.fetchers.coingecko import CoinGeckoFetcher

MOCK_RESPONSE = {
    "solana": {
        "usd": 145.50,
        "usd_24h_change": 3.2,
        "usd_7d_change": -1.5,
        "usd_30d_change": 12.8,
        "usd_24h_vol": 2500000000,
        "usd_market_cap": 65000000000,
    }
}

@pytest.fixture
def fetcher():
    cache = MemoryCache()
    client = httpx.AsyncClient()
    return CoinGeckoFetcher(cache=cache, http_client=client, api_key="")

def test_parse_response(fetcher):
    metrics = fetcher.parse_response(MOCK_RESPONSE)
    names = {m["metric_name"] for m in metrics}
    assert "sol_price" in names
    price = next(m for m in metrics if m["metric_name"] == "sol_price")
    assert price["value"] == 145.50
    assert price["metadata"]["change_24h"] == 3.2
    assert price["metadata"]["change_7d"] == -1.5
    assert price["metadata"]["change_30d"] == 12.8

def test_source_name(fetcher):
    assert fetcher.source_name == "coingecko"
