# backend/tests/test_launch_enrichment.py
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select
from app.database import init_db, get_session
from app.launch.models import LaunchToken


def _make_dexscreener_response(address: str, mcap: float, volume_h1: float, buys: int, sells: int, liquidity: float):
    """Build a minimal DexScreener /tokens/v1/solana response for one token."""
    return [
        {
            "baseToken": {"address": address},
            "dexId": "pumpswap",
            "marketCap": mcap,
            "volume": {"h1": volume_h1, "h6": volume_h1 * 3, "h24": volume_h1 * 10},
            "txns": {
                "h1": {"buys": buys, "sells": sells},
                "h24": {"buys": buys * 10, "sells": sells * 10},
            },
            "liquidity": {"usd": liquidity},
        }
    ]


@pytest.mark.asyncio
async def test_enrich_updates_token_data():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    now = datetime.now(timezone.utc)

    async with get_session(engine) as session:
        session.add(LaunchToken(
            address="TokenA",
            pair_address="PairA",
            launchpad="pumpfun",
            dex="pumpswap",
            created_at=now - timedelta(minutes=30),
        ))
        await session.commit()

    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = _make_dexscreener_response(
        "TokenA", mcap=50000, volume_h1=2000, buys=100, sells=50, liquidity=5000,
    )
    mock_response.raise_for_status = MagicMock()
    mock_http.get.return_value = mock_response

    from app.launch.enrichment import enrich_tracked_tokens
    updated = await enrich_tracked_tokens(engine, mock_http)

    assert updated == 1
    async with get_session(engine) as session:
        result = await session.execute(select(LaunchToken).where(LaunchToken.address == "TokenA"))
        token = result.scalar_one()
        assert token.mcap_current == 50000
        assert token.liquidity_usd == 5000
        assert token.is_alive is True  # volume_h1=2000 > $100
    await engine.dispose()


@pytest.mark.asyncio
async def test_enrich_skips_complete_tokens():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    now = datetime.now(timezone.utc)

    async with get_session(engine) as session:
        session.add(LaunchToken(
            address="TokenB",
            pair_address="PairB",
            launchpad="pumpfun",
            dex="pumpswap",
            created_at=now - timedelta(days=8),
            checkpoint_complete=True,
        ))
        await session.commit()

    mock_http = AsyncMock()

    from app.launch.enrichment import enrich_tracked_tokens
    updated = await enrich_tracked_tokens(engine, mock_http)

    assert updated == 0  # Should not fetch data for complete tokens
    mock_http.get.assert_not_called()
    await engine.dispose()


@pytest.mark.asyncio
async def test_enrich_tracks_peak_mcap():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    now = datetime.now(timezone.utc)

    async with get_session(engine) as session:
        session.add(LaunchToken(
            address="TokenC",
            pair_address="PairC",
            launchpad="pumpfun",
            dex="pumpswap",
            created_at=now - timedelta(minutes=30),
            mcap_current=30000,
            mcap_peak_1h=40000,  # Previous peak was 40k
        ))
        await session.commit()

    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = _make_dexscreener_response(
        "TokenC", mcap=50000, volume_h1=1000, buys=50, sells=30, liquidity=3000,
    )
    mock_response.raise_for_status = MagicMock()
    mock_http.get.return_value = mock_response

    from app.launch.enrichment import enrich_tracked_tokens
    await enrich_tracked_tokens(engine, mock_http)

    async with get_session(engine) as session:
        result = await session.execute(select(LaunchToken).where(LaunchToken.address == "TokenC"))
        token = result.scalar_one()
        # Peak should be updated to 50k since it's higher than previous 40k
        assert token.mcap_peak_1h == 50000
    await engine.dispose()


@pytest.mark.asyncio
async def test_enrich_marks_dead_token():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    now = datetime.now(timezone.utc)

    async with get_session(engine) as session:
        session.add(LaunchToken(
            address="TokenD",
            pair_address="PairD",
            launchpad="pumpfun",
            dex="pumpswap",
            created_at=now - timedelta(hours=2),
            is_alive=True,
        ))
        await session.commit()

    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = _make_dexscreener_response(
        "TokenD", mcap=100, volume_h1=50, buys=2, sells=1, liquidity=50,
    )
    mock_response.raise_for_status = MagicMock()
    mock_http.get.return_value = mock_response

    from app.launch.enrichment import enrich_tracked_tokens
    await enrich_tracked_tokens(engine, mock_http)

    async with get_session(engine) as session:
        result = await session.execute(select(LaunchToken).where(LaunchToken.address == "TokenD"))
        token = result.scalar_one()
        assert token.is_alive is False  # volume_h1=50 < $100
    await engine.dispose()
