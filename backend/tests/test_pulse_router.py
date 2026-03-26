# backend/tests/test_pulse_router.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.cache import MemoryCache
from app.routers.pulse import router as pulse_router, set_cache


@pytest.fixture(autouse=True)
def reset_pulse_cache():
    """Reset the pulse router's global cache after each test to prevent state leakage."""
    yield
    set_cache(MemoryCache())


def _make_test_app():
    """Create a minimal test app with only the pulse router (no lifespan/fetchers)."""
    test_app = FastAPI()
    test_app.include_router(pulse_router)
    cache = MemoryCache()
    set_cache(cache)
    return test_app, cache

def test_pulse_endpoint_returns_structure_empty_cache():
    """Test that /api/pulse returns the expected shape with no cached data."""
    test_app, _ = _make_test_app()
    client = TestClient(test_app)
    resp = client.get("/api/pulse")
    assert resp.status_code == 200
    data = resp.json()
    assert "health_score" in data
    assert "sol_price" in data
    assert "tps" in data
    assert "priority_fees" in data
    assert "stablecoin_supply" in data
    assert "dex_volume" in data
    assert "tvl" in data
    assert "stablecoin_flows" in data
    assert "fear_greed" in data
    assert "google_trends" in data
    assert "last_updated" in data
    # With empty cache, all data fields should be None
    assert data["sol_price"] is None
    assert data["health_score"]["factors_available"] == 0

def test_pulse_endpoint_with_cached_data():
    """Test that /api/pulse populates from cache correctly."""
    test_app, cache = _make_test_app()
    cache.set("coingecko:sol_price", {
        "metric_name": "sol_price", "value": 150.0,
        "metadata": {"change_24h": 5.0, "change_7d": -2.0, "change_30d": 10.0},
        "fetched_at": "2026-01-01T00:00:00Z",
    }, ttl=600)
    cache.set("fear_greed:fear_greed", {
        "metric_name": "fear_greed", "value": 65,
        "metadata": {"label": "Greed"},
        "fetched_at": "2026-01-01T00:00:00Z",
    }, ttl=600)
    client = TestClient(test_app)
    resp = client.get("/api/pulse")
    data = resp.json()
    assert data["sol_price"]["value"] == 150.0
    assert data["fear_greed"]["value"] == 65
    assert data["health_score"]["factors_available"] >= 1
