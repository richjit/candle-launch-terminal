# backend/tests/test_dexscreener.py
import pytest
import httpx
from unittest.mock import AsyncMock
from app.cache import MemoryCache
from app.fetchers.dexscreener import DexScreenerFetcher

MOCK_RESPONSE = {
    "pairs": [
        {
            "chainId": "solana",
            "baseToken": {"symbol": "BONK", "name": "Bonk"},
            "quoteToken": {"symbol": "SOL"},
            "priceUsd": "0.00001234",
            "volume": {"h24": 5000000},
            "liquidity": {"usd": 2000000},
            "priceChange": {"h24": 15.5},
            "fdv": 800000000,
            "pairAddress": "ABC123",
        }
    ]
}

@pytest.fixture
def fetcher():
    cache = MemoryCache()
    client = httpx.AsyncClient()
    return DexScreenerFetcher(cache=cache, http_client=client)

def test_parse_response(fetcher):
    metrics = fetcher.parse_response(MOCK_RESPONSE)
    names = {m["metric_name"] for m in metrics}
    assert "top_pairs" in names
    top_pairs = next(m for m in metrics if m["metric_name"] == "top_pairs")
    assert len(top_pairs["metadata"]["pairs"]) == 1
    assert top_pairs["metadata"]["pairs"][0]["symbol"] == "BONK"
    assert top_pairs["metadata"]["pairs"][0]["price_usd"] == 0.00001234
    assert top_pairs["metadata"]["pairs"][0]["volume_24h"] == 5000000

def test_source_name(fetcher):
    assert fetcher.source_name == "dexscreener"
