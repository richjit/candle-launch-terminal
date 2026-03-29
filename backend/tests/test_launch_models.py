# backend/tests/test_launch_models.py
import pytest
from datetime import datetime, date, timezone
from sqlalchemy import select
from app.database import init_db, get_session


@pytest.mark.asyncio
async def test_launch_token_roundtrip():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    from app.launch.models import LaunchToken

    async with get_session(engine) as session:
        token = LaunchToken(
            address="So1abc123pump",
            pair_address="PairXyz789",
            launchpad="pumpfun",
            dex="raydium",
            created_at=datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc),
        )
        session.add(token)
        await session.commit()

        result = await session.execute(
            select(LaunchToken).where(LaunchToken.address == "So1abc123pump")
        )
        saved = result.scalar_one()
        assert saved.launchpad == "pumpfun"
        assert saved.is_alive is True
        assert saved.checkpoint_complete is False
        assert saved.mcap_peak_1h is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_launch_token_primary_key_unique():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    from app.launch.models import LaunchToken
    from sqlalchemy.exc import IntegrityError

    async with get_session(engine) as session:
        session.add(LaunchToken(
            address="DuplicateAddr",
            pair_address="Pair1",
            launchpad="pumpfun",
            dex="raydium",
            created_at=datetime.now(timezone.utc),
        ))
        await session.commit()
    async with get_session(engine) as session:
        session.add(LaunchToken(
            address="DuplicateAddr",
            pair_address="Pair2",
            launchpad="bonk",
            dex="meteora",
            created_at=datetime.now(timezone.utc),
        ))
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_launch_daily_stats_roundtrip():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    from app.launch.models import LaunchDailyStats

    async with get_session(engine) as session:
        row = LaunchDailyStats(
            date=date(2026, 3, 28),
            launchpad="pumpfun",
            tokens_created=1500,
            tokens_migrated=45,
            migration_rate=0.03,
            total_launches=45,
        )
        session.add(row)
        await session.commit()

        result = await session.execute(
            select(LaunchDailyStats).where(
                LaunchDailyStats.date == date(2026, 3, 28),
                LaunchDailyStats.launchpad == "pumpfun",
            )
        )
        saved = result.scalar_one()
        assert saved.tokens_created == 1500
        assert saved.migration_rate == pytest.approx(0.03)
    await engine.dispose()


@pytest.mark.asyncio
async def test_launch_daily_stats_unique_constraint():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    from app.launch.models import LaunchDailyStats
    from sqlalchemy.exc import IntegrityError

    async with get_session(engine) as session:
        session.add(LaunchDailyStats(
            date=date(2026, 3, 28), launchpad="pumpfun",
            tokens_created=100, tokens_migrated=5, migration_rate=0.05, total_launches=5,
        ))
        await session.commit()
    async with get_session(engine) as session:
        session.add(LaunchDailyStats(
            date=date(2026, 3, 28), launchpad="pumpfun",
            tokens_created=200, tokens_migrated=10, migration_rate=0.05, total_launches=10,
        ))
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()
