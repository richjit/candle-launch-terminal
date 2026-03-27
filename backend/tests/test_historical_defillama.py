import pytest
import httpx
import respx
from datetime import date
from sqlalchemy import select, func
from app.database import init_db, get_session, HistoricalData
from app.ingestion.historical_defillama import (
    ingest_tvl_history,
    ingest_dex_volume_history,
    ingest_stablecoin_history,
)

@pytest.mark.asyncio
@respx.mock
async def test_ingest_tvl_history():
    mock_data = [
        {"date": 1711324800, "tvl": 4000000000},
        {"date": 1711411200, "tvl": 4100000000},
        {"date": 1711497600, "tvl": 4200000000},
    ]
    respx.get("https://api.llama.fi/v2/historicalChainTvl/Solana").mock(
        return_value=httpx.Response(200, json=mock_data)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count = await ingest_tvl_history(engine, client)
    assert count == 3
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData).where(HistoricalData.source == "tvl").order_by(HistoricalData.date)
        )
        rows = result.scalars().all()
        assert len(rows) == 3
        assert rows[2].value == pytest.approx(4.2e9)
    await engine.dispose()

@pytest.mark.asyncio
@respx.mock
async def test_ingest_tvl_skips_if_exists():
    respx.get("https://api.llama.fi/v2/historicalChainTvl/Solana").mock(
        return_value=httpx.Response(200, json=[{"date": 1711324800, "tvl": 4e9}])
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count1 = await ingest_tvl_history(engine, client)
        count2 = await ingest_tvl_history(engine, client)
    assert count1 == 1
    assert count2 == 0
    await engine.dispose()

@pytest.mark.asyncio
@respx.mock
async def test_ingest_dex_volume_history():
    mock_data = {
        "totalDataChart": [
            [1711324800, 500000000],
            [1711411200, 600000000],
        ]
    }
    respx.get("https://api.llama.fi/overview/dexs/solana").mock(
        return_value=httpx.Response(200, json=mock_data)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count = await ingest_dex_volume_history(engine, client)
    assert count == 2
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData).where(HistoricalData.source == "dex_volume").order_by(HistoricalData.date)
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        assert rows[1].value == pytest.approx(6e8)
    await engine.dispose()

@pytest.mark.asyncio
@respx.mock
async def test_ingest_stablecoin_history():
    mock_data = [
        {"date": "1711324800", "totalCirculatingUSD": {"peggedUSD": 3000000000}},
        {"date": "1711411200", "totalCirculatingUSD": {"peggedUSD": 3100000000}},
        {"date": "1711497600", "totalCirculatingUSD": {"peggedUSD": 3200000000}},
    ]
    respx.get("https://stablecoins.llama.fi/stablecoincharts/Solana").mock(
        return_value=httpx.Response(200, json=mock_data)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count = await ingest_stablecoin_history(engine, client)
    assert count == 3
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData).where(HistoricalData.source == "stablecoin_supply").order_by(HistoricalData.date)
        )
        rows = result.scalars().all()
        assert len(rows) == 3
        assert rows[2].value == pytest.approx(3.2e9)
    await engine.dispose()
