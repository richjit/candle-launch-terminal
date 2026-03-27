# backend/tests/test_database.py
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.database import init_db, get_session, MetricData

@pytest.mark.asyncio
async def test_write_and_read_metric():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session(engine) as session:
        metric = MetricData(
            source="test_source",
            metric_name="test_metric",
            value=42.5,
            metadata_json='{"extra": "data"}',
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(metric)
        await session.commit()

        result = await session.execute(
            select(MetricData).where(MetricData.source == "test_source")
        )
        row = result.scalar_one()
        assert row.metric_name == "test_metric"
        assert row.value == 42.5

@pytest.mark.asyncio
async def test_latest_metric_query():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session(engine) as session:
        for i, val in enumerate([10.0, 20.0, 30.0]):
            metric = MetricData(
                source="sol_rpc",
                metric_name="tps",
                value=val,
                fetched_at=datetime(2026, 1, 1, 0, i, 0, tzinfo=timezone.utc),
            )
            session.add(metric)
        await session.commit()

        result = await session.execute(
            select(MetricData)
            .where(MetricData.source == "sol_rpc", MetricData.metric_name == "tps")
            .order_by(MetricData.fetched_at.desc())
            .limit(1)
        )
        latest = result.scalar_one()
        assert latest.value == 30.0


import pytest
from datetime import date, datetime, timezone
from sqlalchemy import select
from app.database import init_db, get_session, DailyScore, HistoricalData


@pytest.mark.asyncio
async def test_daily_score_roundtrip():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session(engine) as session:
        row = DailyScore(
            date=date(2024, 1, 15),
            score=67.3,
            factors_json='{"tvl": {"value": 4e9, "z_score": 0.5, "weight": 0.28, "contribution": 3.2}}',
            factors_available=3,
            factors_total=4,
        )
        session.add(row)
        await session.commit()

        result = await session.execute(select(DailyScore).where(DailyScore.date == date(2024, 1, 15)))
        saved = result.scalar_one()
        assert saved.score == pytest.approx(67.3)
        assert saved.factors_available == 3
        assert saved.factors_total == 4
    await engine.dispose()


@pytest.mark.asyncio
async def test_daily_score_unique_date():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session(engine) as session:
        session.add(DailyScore(date=date(2024, 1, 15), score=67.3, factors_json="{}", factors_available=3, factors_total=4))
        await session.commit()
    async with get_session(engine) as session:
        from sqlalchemy.exc import IntegrityError
        session.add(DailyScore(date=date(2024, 1, 15), score=70.0, factors_json="{}", factors_available=3, factors_total=4))
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_historical_data_roundtrip():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session(engine) as session:
        row = HistoricalData(
            source="sol_ohlcv",
            date=date(2024, 1, 15),
            value=185.50,
            metadata_json='{"open": 183.0, "high": 192.1, "low": 182.5, "close": 185.5}',
        )
        session.add(row)
        await session.commit()

        result = await session.execute(
            select(HistoricalData).where(
                HistoricalData.source == "sol_ohlcv",
                HistoricalData.date == date(2024, 1, 15),
            )
        )
        saved = result.scalar_one()
        assert saved.value == pytest.approx(185.50)
        assert saved.source == "sol_ohlcv"
    await engine.dispose()
