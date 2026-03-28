# backend/tests/test_launch_aggregation.py
import pytest
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from app.database import init_db, get_session
from app.launch.models import LaunchToken, LaunchDailyStats


@pytest.mark.asyncio
async def test_aggregate_computes_daily_stats():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    d = date(2026, 3, 27)

    async with get_session(engine) as session:
        for i, (peak, alive, vol) in enumerate([
            (50000, True, 2000),
            (30000, True, 1500),
            (10000, False, 50),
        ]):
            session.add(LaunchToken(
                address=f"Token{i}",
                pair_address=f"Pair{i}",
                launchpad="pumpfun",
                dex="pumpswap",
                created_at=datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc),
                mcap_peak_1h=peak,
                mcap_peak_24h=peak * 1.5,
                time_to_peak_minutes=30 + i * 10,
                volume_1h=vol,
                buys_1h=100,
                sells_1h=50,
                is_alive=alive,
                checkpoint_complete=True,
            ))
        await session.commit()

    from app.launch.aggregation import aggregate_launch_stats
    count = await aggregate_launch_stats(engine)

    assert count >= 1
    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchDailyStats).where(
                LaunchDailyStats.date == d,
                LaunchDailyStats.launchpad == "pumpfun",
            )
        )
        stats = result.scalar_one()
        assert stats.total_launches == 3
        assert stats.median_peak_mcap_1h == 30000  # Median of [10k, 30k, 50k]
        assert stats.survival_rate_1h is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_aggregate_creates_all_row():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    d = date(2026, 3, 27)

    async with get_session(engine) as session:
        session.add(LaunchToken(
            address="TokenX", pair_address="PairX",
            launchpad="pumpfun", dex="pumpswap",
            created_at=datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc),
            mcap_peak_1h=50000, checkpoint_complete=True,
        ))
        await session.commit()

    from app.launch.aggregation import aggregate_launch_stats
    await aggregate_launch_stats(engine)

    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchDailyStats).where(
                LaunchDailyStats.date == d,
                LaunchDailyStats.launchpad == "all",
            )
        )
        all_stats = result.scalar_one()
        assert all_stats.total_launches == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_cleanup_removes_old_complete_tokens():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=100)).date()

    async with get_session(engine) as session:
        session.add(LaunchToken(
            address="OldToken", pair_address="OldPair",
            launchpad="pumpfun", dex="pumpswap",
            created_at=now - timedelta(days=100),
            checkpoint_complete=True,
        ))
        session.add(LaunchDailyStats(
            date=old_date, launchpad="all",
            tokens_created=100, tokens_migrated=5, migration_rate=0.05, total_launches=5,
        ))
        session.add(LaunchToken(
            address="RecentToken", pair_address="RecentPair",
            launchpad="pumpfun", dex="pumpswap",
            created_at=now - timedelta(days=30),
            checkpoint_complete=True,
        ))
        session.add(LaunchToken(
            address="IncompleteToken", pair_address="IncompletePair",
            launchpad="pumpfun", dex="pumpswap",
            created_at=now - timedelta(days=100),
            checkpoint_complete=False,
        ))
        await session.commit()

    from app.launch.aggregation import cleanup_old_tokens
    deleted = await cleanup_old_tokens(engine)

    assert deleted == 1
    async with get_session(engine) as session:
        result = await session.execute(select(LaunchToken))
        remaining = result.scalars().all()
        addresses = {t.address for t in remaining}
        assert "OldToken" not in addresses
        assert "RecentToken" in addresses
        assert "IncompleteToken" in addresses
    await engine.dispose()
