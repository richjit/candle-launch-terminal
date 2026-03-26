# backend/tests/test_fear_greed.py
import pytest
import httpx
from app.cache import MemoryCache
from app.fetchers.fear_greed import FearGreedFetcher

MOCK_RESPONSE = {
    "data": [
        {"value": "25", "value_classification": "Extreme Fear", "timestamp": "1700000000"}
    ]
}

@pytest.fixture
def fetcher():
    return FearGreedFetcher(cache=MemoryCache(), http_client=httpx.AsyncClient())

def test_parse_response(fetcher):
    metrics = fetcher.parse_response(MOCK_RESPONSE)
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "fear_greed"
    assert metrics[0]["value"] == 25
    assert metrics[0]["metadata"]["label"] == "Extreme Fear"

def test_source_name(fetcher):
    assert fetcher.source_name == "fear_greed"
