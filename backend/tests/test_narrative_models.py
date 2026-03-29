import pytest
from datetime import datetime, timezone
from app.database import init_db, get_session
from app.narrative.models import NarrativeToken, Narrative


@pytest.mark.asyncio
async def test_create_narrative_token():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session(engine) as session:
        token = NarrativeToken(
            address="So1abc123pump",
            name="DogAI",
            symbol="DOGAI",
            pair_address="pair123",
            narrative="AI",
            mcap=50000.0,
            price_change_pct=250.0,
            volume_24h=100000.0,
            liquidity_usd=10000.0,
            is_original=True,
            created_at=datetime.now(timezone.utc),
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
        )
        session.add(token)
        await session.commit()

        from sqlalchemy import select
        result = await session.execute(select(NarrativeToken))
        saved = result.scalar_one()
        assert saved.name == "DogAI"
        assert saved.narrative == "AI"
        assert saved.is_original is True
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_narrative():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with get_session(engine) as session:
        narrative = Narrative(
            name="AI",
            token_count=15,
            total_volume=500000.0,
            avg_gain_pct=180.0,
            top_token_address="So1abc123pump",
            lifecycle="trending",
            last_updated=datetime.now(timezone.utc),
        )
        session.add(narrative)
        await session.commit()

        from sqlalchemy import select
        result = await session.execute(select(Narrative))
        saved = result.scalar_one()
        assert saved.lifecycle == "trending"
        assert saved.token_count == 15
    await engine.dispose()
