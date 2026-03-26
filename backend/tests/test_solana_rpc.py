# backend/tests/test_solana_rpc.py
import pytest
import httpx
from app.cache import MemoryCache
from app.fetchers.solana_rpc import SolanaRpcFetcher

MOCK_TPS_RESPONSE = {
    "jsonrpc": "2.0",
    "result": [
        {"numTransactions": 2500, "numSlots": 1, "samplePeriodSecs": 60},
        {"numTransactions": 2200, "numSlots": 1, "samplePeriodSecs": 60},
    ],
    "id": 1,
}

MOCK_PRIORITY_FEES_RESPONSE = {
    "jsonrpc": "2.0",
    "result": [
        {"slot": 100, "prioritizationFee": 5000},
        {"slot": 101, "prioritizationFee": 8000},
        {"slot": 102, "prioritizationFee": 3000},
    ],
    "id": 1,
}

MOCK_TOKEN_SUPPLY_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "context": {"slot": 100},
        "value": {"amount": "30000000000000", "decimals": 6, "uiAmount": 30000000.0},
    },
    "id": 1,
}

@pytest.fixture
def fetcher():
    cache = MemoryCache()
    client = httpx.AsyncClient()
    return SolanaRpcFetcher(
        cache=cache,
        http_client=client,
        rpc_url="https://api.mainnet-beta.solana.com",
    )

def test_parse_tps(fetcher):
    metrics = fetcher._parse_tps(MOCK_TPS_RESPONSE)
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "tps"
    # TPS = numTransactions / samplePeriodSecs: avg of (2500/60, 2200/60) = ~39.17
    assert metrics[0]["value"] == pytest.approx(39.17, rel=0.01)

def test_parse_priority_fees(fetcher):
    metrics = fetcher._parse_priority_fees(MOCK_PRIORITY_FEES_RESPONSE)
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "priority_fees"
    assert metrics[0]["value"] == pytest.approx(5333.33, rel=0.01)  # average

def test_parse_token_supply(fetcher):
    result = fetcher._parse_token_supply(MOCK_TOKEN_SUPPLY_RESPONSE)
    assert result == pytest.approx(30000000.0)

def test_source_name(fetcher):
    assert fetcher.source_name == "solana_rpc"
