import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.database import init_db, get_session
from app.narrative.models import NarrativeToken, Narrative


@pytest_asyncio.fixture
async def app_with_data():
    engine = await init_db("sqlite+aiosqlite:///:memory:")

    from app.routers.narrative import router, set_engine
    set_engine(engine)

    app = FastAPI()
    app.include_router(router)

    async with get_session(engine) as session:
        session.add(Narrative(
            name="AI", token_count=10, total_volume=500000,
            avg_gain_pct=150.0, top_token_address="ai_token_1",
            lifecycle="trending", last_updated=datetime.now(timezone.utc),
        ))
        session.add(Narrative(
            name="Pets", token_count=5, total_volume=200000,
            avg_gain_pct=80.0, top_token_address="pet_token_1",
            lifecycle="emerging", last_updated=datetime.now(timezone.utc),
        ))
        session.add(NarrativeToken(
            address="ai_token_1", name="SmartAI", symbol="SAI",
            pair_address="pair1", narrative="AI", mcap=100000,
            price_change_pct=300.0, volume_24h=200000, liquidity_usd=50000,
            is_original=True, created_at=datetime.now(timezone.utc),
            first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc),
        ))
        session.add(NarrativeToken(
            address="pet_token_1", name="DogCoin", symbol="DOG",
            pair_address="pair2", narrative="Pets", mcap=50000,
            price_change_pct=120.0, volume_24h=80000, liquidity_usd=20000,
            is_original=True, created_at=datetime.now(timezone.utc),
            first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc),
        ))
        await session.commit()

    yield app
    await engine.dispose()


@pytest.mark.asyncio
async def test_overview(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/narrative/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "narratives" in data
    assert "top_runners" in data
    assert len(data["narratives"]) == 2
    assert data["narratives"][0]["name"] == "AI"


@pytest.mark.asyncio
async def test_narrative_detail(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/narrative/AI")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "AI"
    assert len(data["tokens"]) == 1
    assert data["tokens"][0]["symbol"] == "SAI"
