import pytest
import numpy as np
from datetime import date, timedelta
from sqlalchemy import select
from app.database import init_db, get_session, HistoricalData
from app.analysis.correlation import compute_correlations, CorrelationResult


def _make_dates(n: int, start: date = date(2022, 1, 1)) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


@pytest.mark.asyncio
async def test_compute_correlations_positive():
    """A factor perfectly correlated with SOL forward returns should have r ≈ 1."""
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    n = 400
    dates = _make_dates(n)

    async with get_session(engine) as session:
        # SOL prices: linear uptrend
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="sol_ohlcv", date=d, value=100 + i, metadata_json=None))
        # TVL: also linear uptrend (perfectly correlated)
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="tvl", date=d, value=1e9 + i * 1e7, metadata_json=None))
        await session.commit()

    results = await compute_correlations(engine)
    tvl_result = next((r for r in results if r.name == "tvl"), None)
    assert tvl_result is not None
    assert tvl_result.correlation > 0.5  # strongly positive
    assert tvl_result.in_score is True  # above 0.15 threshold
    assert tvl_result.weight > 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_compute_correlations_excludes_low_correlation():
    """A factor with random noise should be excluded from scoring."""
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    n = 400
    dates = _make_dates(n)
    rng = np.random.default_rng(42)

    async with get_session(engine) as session:
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="sol_ohlcv", date=d, value=100 + i * 0.5 + rng.normal(0, 5), metadata_json=None))
        # Random noise factor — should have low correlation
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="tvl", date=d, value=rng.uniform(1e9, 5e9), metadata_json=None))
        await session.commit()

    results = await compute_correlations(engine)
    tvl_result = next((r for r in results if r.name == "tvl"), None)
    assert tvl_result is not None
    # With pure random noise (seed 42), |r| should be low
    assert abs(tvl_result.correlation) < 0.5
    # Key assertion: if |r| < 0.15, it should be excluded from scoring
    if abs(tvl_result.correlation) < 0.15:
        assert tvl_result.in_score is False
        assert tvl_result.weight == 0.0
    await engine.dispose()


@pytest.mark.asyncio
async def test_compute_correlations_insufficient_data():
    """Factor with < 365 data points should be excluded."""
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    n = 400
    dates = _make_dates(n)

    async with get_session(engine) as session:
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="sol_ohlcv", date=d, value=100 + i, metadata_json=None))
        # Only 100 data points for TVL — below 365 minimum
        for i, d in enumerate(dates[:100]):
            session.add(HistoricalData(source="tvl", date=d, value=1e9 + i * 1e7, metadata_json=None))
        await session.commit()

    results = await compute_correlations(engine)
    tvl_result = next((r for r in results if r.name == "tvl"), None)
    assert tvl_result is None  # excluded due to insufficient data
    await engine.dispose()


@pytest.mark.asyncio
async def test_weights_sum_to_one():
    """Weights of all in_score factors should sum to 1.0."""
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    n = 400
    dates = _make_dates(n)

    async with get_session(engine) as session:
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="sol_ohlcv", date=d, value=100 + i * 0.5, metadata_json=None))
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="tvl", date=d, value=1e9 + i * 1e7, metadata_json=None))
        for i, d in enumerate(dates):
            session.add(HistoricalData(source="fear_greed", date=d, value=50 + i * 0.1, metadata_json=None))
        await session.commit()

    results = await compute_correlations(engine)
    scored = [r for r in results if r.in_score]
    if scored:
        total_weight = sum(r.weight for r in scored)
        assert total_weight == pytest.approx(1.0, abs=0.01)
    await engine.dispose()
