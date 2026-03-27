import pytest
import json
import numpy as np
from datetime import date, timedelta
from sqlalchemy import select, func
from app.database import init_db, get_session, HistoricalData, DailyScore
from app.analysis.correlation import CorrelationResult
from app.analysis.score_backfill import backfill_scores


def _make_dates(n: int, start: date = date(2022, 1, 1)) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


@pytest.mark.asyncio
async def test_backfill_scores_creates_daily_scores():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    n = 200
    dates = _make_dates(n)

    async with get_session(engine) as session:
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="sol_ohlcv", date=d, value=100 + i, metadata_json=None))
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="tvl", date=d, value=1e9 + i * 1e7, metadata_json=None))
        await session.commit()

    correlations = [
        CorrelationResult(name="tvl", label="TVL", correlation=0.42, optimal_lag_days=3, weight=1.0, in_score=True),
    ]

    count = await backfill_scores(engine, correlations)
    assert count > 0

    async with get_session(engine) as session:
        result = await session.execute(select(func.count()).select_from(DailyScore))
        total = result.scalar()
        assert total == count
        assert total > 0

        # Check a score is in valid range
        result = await session.execute(select(DailyScore).limit(1))
        row = result.scalar_one()
        assert 0 <= row.score <= 100
        assert row.factors_available >= 1
        factors = json.loads(row.factors_json)
        assert "tvl" in factors
    await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_scores_idempotent():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    n = 200
    dates = _make_dates(n)

    async with get_session(engine) as session:
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="sol_ohlcv", date=d, value=100 + i, metadata_json=None))
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="tvl", date=d, value=1e9 + i * 1e7, metadata_json=None))
        await session.commit()

    correlations = [
        CorrelationResult(name="tvl", label="TVL", correlation=0.42, optimal_lag_days=3, weight=1.0, in_score=True),
    ]

    count1 = await backfill_scores(engine, correlations)
    count2 = await backfill_scores(engine, correlations)
    assert count1 > 0
    assert count2 == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_score_uses_90_day_rolling_window():
    """Scores should use 90-day rolling z-scores, not global stats."""
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    n = 200
    dates = _make_dates(n)

    async with get_session(engine) as session:
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="sol_ohlcv", date=d, value=100 + i, metadata_json=None))
        # TVL: flat then spike
        for i, d in enumerate(dates):
            val = 1e9 if i < 150 else 5e9
            session.add(HistoricalData(source="tvl", date=d, value=val, metadata_json=None))
        await session.commit()

    correlations = [
        CorrelationResult(name="tvl", label="TVL", correlation=0.42, optimal_lag_days=3, weight=1.0, in_score=True),
    ]

    await backfill_scores(engine, correlations)

    async with get_session(engine) as session:
        # Score at day 160 should be high (spike above rolling mean)
        result = await session.execute(
            select(DailyScore).where(DailyScore.date == dates[160])
        )
        spike_score = result.scalar_one()
        # Score at day 100 should be neutral (flat period)
        result = await session.execute(
            select(DailyScore).where(DailyScore.date == dates[100])
        )
        flat_score = result.scalar_one()
        assert spike_score.score > flat_score.score
    await engine.dispose()
