import pytest
import httpx
import respx
from datetime import date
from sqlalchemy import select, func
from app.database import init_db, get_session, HistoricalData
from app.ingestion.historical_fng import ingest_fear_greed_history

MOCK_FNG_RESPONSE = {
    "data": [
        {"value": "75", "value_classification": "Greed", "timestamp": "1711497600"},
        {"value": "60", "value_classification": "Greed", "timestamp": "1711411200"},
        {"value": "45", "value_classification": "Fear", "timestamp": "1711324800"},
    ]
}

@pytest.mark.asyncio
@respx.mock
async def test_ingest_fng_history():
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(200, json=MOCK_FNG_RESPONSE)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count = await ingest_fear_greed_history(engine, client)
    assert count == 3
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData).where(HistoricalData.source == "fear_greed").order_by(HistoricalData.date)
        )
        rows = result.scalars().all()
        assert len(rows) == 3
        assert rows[2].value == pytest.approx(75.0)
    await engine.dispose()

@pytest.mark.asyncio
@respx.mock
async def test_ingest_fng_skips_if_exists():
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(200, json=MOCK_FNG_RESPONSE)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count1 = await ingest_fear_greed_history(engine, client)
        count2 = await ingest_fear_greed_history(engine, client)
    assert count1 == 3
    assert count2 == 0
    await engine.dispose()
