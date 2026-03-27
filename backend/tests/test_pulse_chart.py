import pytest
import json
from datetime import date, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import init_db, get_session, HistoricalData, DailyScore
from app.routers.pulse_chart import router, set_engine


def _make_app(engine):
    app = FastAPI()
    app.include_router(router)
    set_engine(engine)
    return app


@pytest.mark.asyncio
async def test_chart_endpoint_returns_candles_and_scores():
    engine = await init_db("sqlite+aiosqlite:///:memory:")

    async with get_session(engine) as session:
        base = date(2026, 2, 1)
        for i in range(60):
            d = base + timedelta(days=i)
            session.add(HistoricalData(
                source="sol_ohlcv", date=d, value=180 + i,
                metadata_json=json.dumps({"open": 179+i, "high": 185+i, "low": 175+i, "close": 180+i}),
            ))
            session.add(DailyScore(
                date=d, score=50 + i * 0.5,
                factors_json="{}", factors_available=3, factors_total=4,
            ))
        await session.commit()

    client = TestClient(_make_app(engine))
    resp = client.get("/api/pulse/chart?range=30d")
    assert resp.status_code == 200
    data = resp.json()
    assert "candles" in data
    assert "scores" in data
    assert data["range"] == "30d"
    assert len(data["candles"]) == 30
    assert len(data["scores"]) == 30
    # Check candle structure
    candle = data["candles"][0]
    assert "time" in candle
    assert "open" in candle
    assert "high" in candle
    assert "low" in candle
    assert "close" in candle
    # Check score structure
    score = data["scores"][0]
    assert "time" in score
    assert "score" in score
    await engine.dispose()


@pytest.mark.asyncio
async def test_chart_endpoint_range_all():
    engine = await init_db("sqlite+aiosqlite:///:memory:")

    async with get_session(engine) as session:
        base = date(2022, 1, 1)
        for i in range(100):
            d = base + timedelta(days=i)
            session.add(HistoricalData(
                source="sol_ohlcv", date=d, value=100 + i,
                metadata_json=json.dumps({"open": 99+i, "high": 105+i, "low": 95+i, "close": 100+i}),
            ))
            session.add(DailyScore(
                date=d, score=50.0,
                factors_json="{}", factors_available=2, factors_total=4,
            ))
        await session.commit()

    client = TestClient(_make_app(engine))
    resp = client.get("/api/pulse/chart?range=all")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candles"]) == 100
    assert data["range"] == "all"
    await engine.dispose()


@pytest.mark.asyncio
async def test_chart_endpoint_invalid_range():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    client = TestClient(_make_app(engine))
    resp = client.get("/api/pulse/chart?range=5d")
    assert resp.status_code == 400
    await engine.dispose()
