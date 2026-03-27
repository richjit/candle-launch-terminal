# backend/tests/test_google_trends.py
import pytest
import httpx
from app.cache import MemoryCache
from app.fetchers.google_trends import GoogleTrendsFetcher

@pytest.fixture
def fetcher():
    return GoogleTrendsFetcher(cache=MemoryCache(), http_client=httpx.AsyncClient())

def test_parse_response(fetcher):
    # Simulate pytrends-like response
    mock_data = {"solana": 75, "ethereum": 60, "bitcoin": 90}
    metrics = fetcher.parse_response(mock_data)
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "google_trends"
    assert metrics[0]["metadata"]["solana"] == 75
    assert metrics[0]["metadata"]["ethereum"] == 60
    assert metrics[0]["metadata"]["bitcoin"] == 90

def test_source_name(fetcher):
    assert fetcher.source_name == "google_trends"
