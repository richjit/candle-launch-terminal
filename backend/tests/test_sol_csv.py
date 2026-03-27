import pytest
import tempfile
import os
from datetime import date
from sqlalchemy import select, func
from app.database import init_db, get_session, HistoricalData
from app.ingestion.sol_csv import ingest_sol_csv


@pytest.mark.asyncio
async def test_ingest_sol_csv_parses_correctly():
    csv_content = (
        "time,open,high,low,close,#1\n"
        "1586476800,0.21464622,1.33977149,0.21379166,0.94799898,\n"
        "1586563200,0.94799013,1.06113905,0.76209019,0.78910001,\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        count = await ingest_sol_csv(engine, csv_path)
        assert count == 2
        async with get_session(engine) as session:
            result = await session.execute(
                select(HistoricalData).where(HistoricalData.source == "sol_ohlcv").order_by(HistoricalData.date)
            )
            rows = result.scalars().all()
            assert len(rows) == 2
            assert rows[0].date == date(2020, 4, 10)
            assert rows[0].value == pytest.approx(0.94799898, rel=1e-5)
        await engine.dispose()
    finally:
        os.unlink(csv_path)


@pytest.mark.asyncio
async def test_ingest_sol_csv_skips_if_already_ingested():
    csv_content = (
        "time,open,high,low,close,#1\n"
        "1586476800,0.21464622,1.33977149,0.21379166,0.94799898,\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        count1 = await ingest_sol_csv(engine, csv_path)
        count2 = await ingest_sol_csv(engine, csv_path)
        assert count1 == 1
        assert count2 == 0
        async with get_session(engine) as session:
            result = await session.execute(
                select(func.count()).select_from(HistoricalData).where(HistoricalData.source == "sol_ohlcv")
            )
            assert result.scalar() == 1
        await engine.dispose()
    finally:
        os.unlink(csv_path)


@pytest.mark.asyncio
async def test_ingest_sol_csv_stores_ohlc_metadata():
    csv_content = (
        "time,open,high,low,close,#1\n"
        "1711497600,185.20,192.10,183.00,190.50,\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        await ingest_sol_csv(engine, csv_path)
        async with get_session(engine) as session:
            result = await session.execute(select(HistoricalData).where(HistoricalData.source == "sol_ohlcv"))
            row = result.scalar_one()
            import json
            meta = json.loads(row.metadata_json)
            assert meta["open"] == pytest.approx(185.20)
            assert meta["high"] == pytest.approx(192.10)
            assert meta["low"] == pytest.approx(183.00)
            assert meta["close"] == pytest.approx(190.50)
        await engine.dispose()
    finally:
        os.unlink(csv_path)
