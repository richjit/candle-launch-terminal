# backend/tests/test_defillama.py
import pytest
import httpx
from app.cache import MemoryCache
from app.fetchers.defillama import DefiLlamaFetcher

MOCK_TVL_RESPONSE = [
    {"date": 1700000000, "tvl": 4500000000},
    {"date": 1700086400, "tvl": 4600000000},
]

MOCK_DEX_VOLUME_RESPONSE = {
    "totalDataChart": [
        [1700000000, 500000000],
        [1700086400, 600000000],
    ],
    "total24h": 600000000,
}

MOCK_CHAINS_TVL = [
    {"name": "Ethereum", "tvl": 50000000000},
    {"name": "Solana", "tvl": 5000000000},
    {"name": "Base", "tvl": 3000000000},
]

MOCK_STABLECOINS_RESPONSE = {
    "chains": [
        {"name": "Solana", "totalCirculatingUSD": {"peggedUSD": 5000000000}},
        {"name": "Ethereum", "totalCirculatingUSD": {"peggedUSD": 80000000000}},
    ]
}

@pytest.fixture
def fetcher():
    cache = MemoryCache()
    client = httpx.AsyncClient()
    return DefiLlamaFetcher(cache=cache, http_client=client)

def test_parse_response(fetcher):
    data = {
        "tvl_history": MOCK_TVL_RESPONSE,
        "dex_volume": MOCK_DEX_VOLUME_RESPONSE,
        "chains_tvl": MOCK_CHAINS_TVL,
        "stablecoins": MOCK_STABLECOINS_RESPONSE,
    }
    metrics = fetcher.parse_response(data)
    names = {m["metric_name"] for m in metrics}
    assert "solana_tvl" in names
    assert "dex_volume_24h" in names
    assert "chains_tvl" in names
    assert "stablecoin_flows" in names

    tvl = next(m for m in metrics if m["metric_name"] == "solana_tvl")
    assert tvl["value"] == 4600000000

    dex_vol = next(m for m in metrics if m["metric_name"] == "dex_volume_24h")
    assert dex_vol["value"] == 600000000

    stables = next(m for m in metrics if m["metric_name"] == "stablecoin_flows")
    assert stables["metadata"]["Solana"] == 5000000000

def test_source_name(fetcher):
    assert fetcher.source_name == "defillama"
