import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.cache import MemoryCache
from app.database import init_db
from app.routers.pulse_ecosystem import router, set_cache, set_engine


def _make_app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_ecosystem_returns_live_metrics():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    cache = MemoryCache()
    cache.set("solana_rpc:tps", {"value": 3200, "fetched_at": "2026-03-27T12:00:00Z"}, 600)
    cache.set("solana_rpc:priority_fees", {"value": 5000, "fetched_at": "2026-03-27T12:00:00Z"}, 600)
    cache.set("solana_rpc:stablecoin_supply", {
        "value": 25e9, "metadata": {"usdc": 15e9, "usdt": 10e9},
        "fetched_at": "2026-03-27T12:00:00Z",
    }, 600)
    cache.set("google_trends:google_trends", {
        "value": 0, "metadata": {"solana": 75, "ethereum": 60, "bitcoin": 80},
        "fetched_at": "2026-03-27T12:00:00Z",
    }, 600)
    set_cache(cache)
    set_engine(engine)

    client = TestClient(_make_app())
    resp = client.get("/api/pulse/ecosystem")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "last_updated" in data

    names = [m["name"] for m in data["metrics"]]
    assert "tps" in names
    assert "priority_fees" in names
    # Verify sparkline field exists
    tps_metric = next(m for m in data["metrics"] if m["name"] == "tps")
    assert "sparkline" in tps_metric
    assert isinstance(tps_metric["sparkline"], list)
    await engine.dispose()


@pytest.mark.asyncio
async def test_ecosystem_empty_cache():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    cache = MemoryCache()
    set_cache(cache)
    set_engine(engine)

    client = TestClient(_make_app())
    resp = client.get("/api/pulse/ecosystem")
    assert resp.status_code == 200
    data = resp.json()
    assert data["metrics"] == []
    await engine.dispose()
