import pytest
import pytest_asyncio
from datetime import date, datetime, timezone
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.database import init_db, get_session
from app.launch.models import LaunchDailyStats


@pytest_asyncio.fixture
async def app_with_data():
    """Create a FastAPI app with launch router and seed data."""
    engine = await init_db("sqlite+aiosqlite:///:memory:")

    from app.routers.launch import router, set_engine
    set_engine(engine)

    app = FastAPI()
    app.include_router(router)

    # Seed daily stats
    async with get_session(engine) as session:
        for i in range(7):
            d = date(2026, 3, 22 + i)
            session.add(LaunchDailyStats(
                date=d, launchpad="all",
                tokens_created=1000 + i * 100, tokens_migrated=30 + i * 5,
                migration_rate=0.03 + i * 0.005,
                median_peak_mcap_1h=50000 + i * 5000,
                median_peak_mcap_24h=80000 + i * 8000,
                median_time_to_peak=45.0 + i * 2,
                survival_rate_1h=80.0 - i,
                survival_rate_24h=40.0 - i,
                survival_rate_7d=10.0 - i * 0.5,
                avg_buy_sell_ratio_1h=1.5 + i * 0.1,
                total_launches=30 + i * 5,
                total_volume=500000 + i * 50000,
            ))
            # Also add per-launchpad rows
            session.add(LaunchDailyStats(
                date=d, launchpad="pumpfun",
                tokens_created=800 + i * 80, tokens_migrated=20 + i * 3,
                migration_rate=0.025, total_launches=20 + i * 3,
                median_peak_mcap_1h=40000, median_peak_mcap_24h=60000,
            ))
        await session.commit()

    yield app
    await engine.dispose()


@pytest.mark.asyncio
async def test_overview_endpoint(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/launch/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        # Should have 8 metrics
        assert len(data["metrics"]) == 8
        # Each metric should have current, trend, chart
        for m in data["metrics"]:
            assert "name" in m
            assert "current" in m
            assert "trend" in m
            assert "chart" in m


@pytest.mark.asyncio
async def test_migration_rate_endpoint(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/launch/migration-rate?range=7d")
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data
        assert "chart" in data
        assert "breakdown" in data
        assert "last_updated" in data


@pytest.mark.asyncio
async def test_range_filter(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_7d = await client.get("/api/launch/launches?range=7d")
        resp_30d = await client.get("/api/launch/launches?range=30d")
        assert resp_7d.status_code == 200
        assert resp_30d.status_code == 200


@pytest.mark.asyncio
async def test_invalid_range(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/launch/overview?range=invalid")
        assert resp.status_code == 400
