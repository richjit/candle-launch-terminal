# backend/tests/test_launch_discovery.py
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from app.database import init_db, get_session
from app.launch.models import LaunchToken


# Minimal GeckoTerminal response structure
GECKO_RESPONSE = {
    "data": [
        {
            "id": "solana_pool1",
            "type": "pool",
            "attributes": {
                "address": "PoolAddr1",
                "name": "TESTCOIN / SOL",
                "pool_created_at": "2026-03-28T12:00:00Z",
                "fdv_usd": "50000.0",
                "base_token_price_usd": "0.001",
                "reserve_in_usd": "5000.0",
            },
            "relationships": {
                "base_token": {
                    "data": {"id": "solana_MintAddr1pump", "type": "token"}
                },
                "dex": {
                    "data": {"id": "pumpswap", "type": "dex"}
                },
            },
        },
        {
            # Non-launchpad token — should be skipped
            "id": "solana_pool2",
            "type": "pool",
            "attributes": {
                "address": "PoolAddr2",
                "name": "RANDOM / SOL",
                "pool_created_at": "2026-03-28T12:01:00Z",
                "fdv_usd": "100000.0",
                "base_token_price_usd": "0.01",
                "reserve_in_usd": "10000.0",
            },
            "relationships": {
                "base_token": {
                    "data": {"id": "solana_RandomMintXyz", "type": "token"}
                },
                "dex": {
                    "data": {"id": "raydium", "type": "dex"}
                },
            },
        },
    ]
}


@pytest.mark.asyncio
async def test_discover_creates_launchpad_tokens():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = GECKO_RESPONSE
    mock_response.raise_for_status = MagicMock()
    mock_http.get.return_value = mock_response

    from app.launch.discovery import discover_new_launches
    count = await discover_new_launches(engine, mock_http)

    assert count == 1  # Only the pump.fun token, not the Raydium one

    async with get_session(engine) as session:
        result = await session.execute(select(LaunchToken))
        tokens = result.scalars().all()
        assert len(tokens) == 1
        assert tokens[0].address == "MintAddr1pump"
        assert tokens[0].launchpad == "pumpfun"
    await engine.dispose()


@pytest.mark.asyncio
async def test_discover_skips_existing_tokens():
    engine = await init_db("sqlite+aiosqlite:///:memory:")

    # Pre-insert the token
    async with get_session(engine) as session:
        session.add(LaunchToken(
            address="MintAddr1pump",
            pair_address="PoolAddr1",
            launchpad="pumpfun",
            dex="pumpswap",
            created_at=datetime.now(timezone.utc),
        ))
        await session.commit()

    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = GECKO_RESPONSE
    mock_response.raise_for_status = MagicMock()
    mock_http.get.return_value = mock_response

    from app.launch.discovery import discover_new_launches
    count = await discover_new_launches(engine, mock_http)

    assert count == 0  # Already existed
    await engine.dispose()


@pytest.mark.asyncio
async def test_discover_handles_api_error():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    mock_http = AsyncMock()
    mock_http.get.side_effect = Exception("Connection refused")

    from app.launch.discovery import discover_new_launches
    count = await discover_new_launches(engine, mock_http)

    assert count == 0  # Graceful failure
    await engine.dispose()
