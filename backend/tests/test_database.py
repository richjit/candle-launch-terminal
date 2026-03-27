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
