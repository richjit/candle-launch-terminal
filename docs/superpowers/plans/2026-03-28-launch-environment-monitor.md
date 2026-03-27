# Launch Environment Monitor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a launch intelligence dashboard at `/launch` that tracks Solana token launches across launchpads and shows metrics like migration rate, peak mcap, survival rate, and market context.

**Architecture:** GeckoTerminal discovers new pools, DexScreener enriches token data, standalone APScheduler jobs process and aggregate metrics into two new DB tables (`launch_tokens`, `launch_daily_stats`), a FastAPI router serves 9 endpoints, and a React frontend renders a card grid dashboard with drill-down detail pages.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, APScheduler, httpx, React 18, TypeScript, lightweight-charts, TailwindCSS v4

**Spec:** `docs/superpowers/specs/2026-03-27-launch-environment-monitor-design.md`

---

## File Structure

### Backend — New Files

| File | Responsibility |
|---|---|
| `backend/app/launch/__init__.py` | Package marker |
| `backend/app/launch/models.py` | `LaunchToken` and `LaunchDailyStats` SQLAlchemy models |
| `backend/app/launch/config.py` | Launchpad identification config (program addresses, dexId mappings, address patterns) |
| `backend/app/launch/discovery.py` | `discover_new_launches()` — GeckoTerminal polling, launchpad tagging, new row creation |
| `backend/app/launch/enrichment.py` | `enrich_tracked_tokens()` — DexScreener batch updates, checkpoint snapshots, peak tracking |
| `backend/app/launch/aggregation.py` | `aggregate_launch_stats()` — daily stats computation; `cleanup_old_tokens()` — 90-day retention |
| `backend/app/routers/launch.py` | FastAPI router with 9 endpoints under `/api/launch/` |
| `backend/tests/test_launch_models.py` | Model CRUD and constraint tests |
| `backend/tests/test_launch_config.py` | Launchpad identification tests |
| `backend/tests/test_launch_discovery.py` | GeckoTerminal discovery job tests |
| `backend/tests/test_launch_enrichment.py` | DexScreener enrichment job tests |
| `backend/tests/test_launch_aggregation.py` | Aggregation and cleanup tests |
| `backend/tests/test_launch_api.py` | API endpoint tests |

### Backend — Modified Files

| File | Change |
|---|---|
| `backend/app/database.py` | Import `launch.models` **at the bottom of the file** (after `Base` is defined) so `Base.metadata.create_all` picks up the new tables |
| `backend/app/config.py` | Add `fetch_interval_launch_discovery`, `fetch_interval_launch_enrichment` settings |
| `backend/app/main.py` | Register launch router, schedule discovery/enrichment/aggregation jobs |

### Frontend — New Files

| File | Responsibility |
|---|---|
| `frontend/src/types/launch.ts` | TypeScript interfaces for launch API responses |
| `frontend/src/api/launch.ts` | API fetch functions for all `/api/launch/` endpoints |
| `frontend/src/pages/LaunchDashboard.tsx` | Grid of 8 metric cards with polling |
| `frontend/src/pages/LaunchDetail.tsx` | Shared detail page layout with chart, range selector, breakdown slot |
| `frontend/src/components/launch/LaunchMetricCard.tsx` | Dashboard tile: value, sparkline, trend arrow, click-to-navigate |
| `frontend/src/components/launch/LaunchBreakdownTable.tsx` | Per-launchpad breakdown table |

### Frontend — Modified Files

| File | Change |
|---|---|
| `frontend/src/App.tsx` | Add `/launch` and `/launch/:metric` routes |

---

## Task 1: Database Models

**Files:**
- Create: `backend/app/launch/__init__.py`
- Create: `backend/app/launch/models.py`
- Modify: `backend/app/database.py`
- Test: `backend/tests/test_launch_models.py`

- [ ] **Step 1: Write failing tests for LaunchToken model**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_launch_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.launch'`

- [ ] **Step 3: Create the launch package and models**

```python
# backend/app/launch/__init__.py
```

```python
# backend/app/launch/models.py
from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class LaunchToken(Base):
    __tablename__ = "launch_tokens"

    address: Mapped[str] = mapped_column(String(60), primary_key=True)
    pair_address: Mapped[str] = mapped_column(String(60))
    launchpad: Mapped[str] = mapped_column(String(30), index=True)
    dex: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mcap_peak_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    mcap_peak_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    mcap_peak_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    mcap_current: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_to_peak_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    buys_1h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sells_1h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buys_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sells_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    liquidity_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    checkpoint_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class LaunchDailyStats(Base):
    __tablename__ = "launch_daily_stats"
    __table_args__ = (
        UniqueConstraint("date", "launchpad", name="uq_launch_date_launchpad"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    launchpad: Mapped[str] = mapped_column(String(30))
    tokens_created: Mapped[int] = mapped_column(Integer)
    tokens_migrated: Mapped[int] = mapped_column(Integer)
    migration_rate: Mapped[float] = mapped_column(Float)
    median_peak_mcap_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_peak_mcap_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_peak_mcap_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_time_to_peak: Mapped[float | None] = mapped_column(Float, nullable=True)
    survival_rate_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    survival_rate_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    survival_rate_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_buy_sell_ratio_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_launches: Mapped[int] = mapped_column(Integer)
    total_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
```

- [ ] **Step 4: Register models with Base so `create_all` picks them up**

Add to the **bottom** of `backend/app/database.py` (after `get_session` — must be after `Base` is defined to avoid circular import):

```python
# Import launch models so Base.metadata includes their tables
import app.launch.models  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_launch_models.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/launch/ backend/app/database.py backend/tests/test_launch_models.py
git commit -m "feat(launch): add LaunchToken and LaunchDailyStats models"
```

---

## Task 2: Launchpad Identification Config

**Files:**
- Create: `backend/app/launch/config.py`
- Test: `backend/tests/test_launch_config.py`

- [ ] **Step 1: Write failing tests for launchpad identification**

```python
# backend/tests/test_launch_config.py
from app.launch.config import identify_launchpad


def test_identify_pumpfun_by_dex_name():
    assert identify_launchpad(dex_name="PumpSwap", token_address="abc123pump", dex_id=None) == "pumpfun"


def test_identify_pumpfun_by_address_suffix():
    assert identify_launchpad(dex_name="Raydium", token_address="So1abc123pump", dex_id=None) == "pumpfun"


def test_identify_pumpfun_by_dex_id():
    assert identify_launchpad(dex_name=None, token_address="abc", dex_id="pumpswap") == "pumpfun"


def test_identify_unknown_returns_none():
    assert identify_launchpad(dex_name="Raydium", token_address="abc123xyz", dex_id="raydium") is None


def test_identify_bonk():
    assert identify_launchpad(dex_name="Bonk Launcher", token_address="abc", dex_id=None) == "bonk"


def test_supported_launchpads_list():
    from app.launch.config import SUPPORTED_LAUNCHPADS
    assert "pumpfun" in SUPPORTED_LAUNCHPADS
    assert "bonk" in SUPPORTED_LAUNCHPADS
    assert "bags" in SUPPORTED_LAUNCHPADS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_launch_config.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement launchpad config**

```python
# backend/app/launch/config.py
"""Launchpad identification configuration.

Maps DEX names, dexIds, and address patterns to canonical launchpad names.
Add new launchpads by extending the dicts below.
"""

# Canonical launchpad name → program address (for RPC counting)
LAUNCHPAD_PROGRAMS: dict[str, str] = {
    "pumpfun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    # "candle": "TBD",  # Candle TV v2 — uncomment when launched
}

# GeckoTerminal DEX name (case-insensitive) → launchpad
DEX_NAME_MAP: dict[str, str] = {
    "pumpswap": "pumpfun",
    "pump.fun": "pumpfun",
    "bonk launcher": "bonk",
    "bonk": "bonk",
    "bags": "bags",
    "candle": "candle",
}

# DexScreener dexId → launchpad
DEX_ID_MAP: dict[str, str] = {
    "pumpswap": "pumpfun",
}

# Token address suffix → launchpad
ADDRESS_SUFFIX_MAP: dict[str, str] = {
    "pump": "pumpfun",
}

SUPPORTED_LAUNCHPADS = {"pumpfun", "bonk", "bags", "candle"}


def identify_launchpad(
    dex_name: str | None = None,
    token_address: str | None = None,
    dex_id: str | None = None,
) -> str | None:
    """Identify which launchpad a token came from using multiple signals.

    Returns canonical launchpad name or None if not from a known launchpad.
    """
    # Check DEX name (from GeckoTerminal)
    if dex_name:
        key = dex_name.lower().strip()
        if key in DEX_NAME_MAP:
            return DEX_NAME_MAP[key]

    # Check dexId (from DexScreener)
    if dex_id:
        key = dex_id.lower().strip()
        if key in DEX_ID_MAP:
            return DEX_ID_MAP[key]

    # Check address suffix
    if token_address:
        for suffix, launchpad in ADDRESS_SUFFIX_MAP.items():
            if token_address.lower().endswith(suffix):
                return launchpad

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_launch_config.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/launch/config.py backend/tests/test_launch_config.py
git commit -m "feat(launch): add launchpad identification config"
```

---

## Task 3: GeckoTerminal Discovery Job

**Files:**
- Create: `backend/app/launch/discovery.py`
- Test: `backend/tests/test_launch_discovery.py`

- [ ] **Step 1: Write failing tests for discovery**

```python
# backend/tests/test_launch_discovery.py
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
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
    mock_response = AsyncMock()
    mock_response.json.return_value = GECKO_RESPONSE
    mock_response.raise_for_status = lambda: None
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
    mock_response = AsyncMock()
    mock_response.json.return_value = GECKO_RESPONSE
    mock_response.raise_for_status = lambda: None
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_launch_discovery.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement discovery job**

```python
# backend/app/launch/discovery.py
"""GeckoTerminal discovery: polls for new Solana pools and creates LaunchToken rows."""
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.database import get_session
from app.launch.config import identify_launchpad
from app.launch.models import LaunchToken

logger = logging.getLogger(__name__)

GECKO_NEW_POOLS_URL = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools"


def _parse_token_address(token_id: str) -> str:
    """Extract mint address from GeckoTerminal token ID like 'solana_MintAddr123'."""
    return token_id.removeprefix("solana_")


def _parse_dex_id(dex_data: dict) -> str:
    """Extract DEX id from GeckoTerminal relationship."""
    return dex_data.get("data", {}).get("id", "")


async def discover_new_launches(engine, http_client: httpx.AsyncClient) -> int:
    """Poll GeckoTerminal for new Solana pools and insert launchpad tokens.

    Returns number of new tokens created.
    """
    try:
        resp = await http_client.get(GECKO_NEW_POOLS_URL, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"GeckoTerminal discovery failed: {e}")
        return 0

    pools = data.get("data", [])
    if not pools:
        return 0

    new_count = 0
    async with get_session(engine) as session:
        # Batch-check which addresses already exist
        candidate_addresses = []
        candidate_pools = []
        for pool in pools:
            rels = pool.get("relationships", {})
            base_token = rels.get("base_token", {})
            token_id = base_token.get("data", {}).get("id", "")
            if not token_id:
                continue

            address = _parse_token_address(token_id)
            dex_id = _parse_dex_id(rels.get("dex", {}))
            attrs = pool.get("attributes", {})
            dex_name = dex_id  # GeckoTerminal uses dex id as name

            launchpad = identify_launchpad(
                dex_name=dex_name,
                token_address=address,
                dex_id=dex_id,
            )
            if not launchpad:
                continue

            candidate_addresses.append(address)
            candidate_pools.append((address, pool, launchpad, dex_id, attrs))

        if not candidate_addresses:
            return 0

        # Check existing
        result = await session.execute(
            select(LaunchToken.address).where(
                LaunchToken.address.in_(candidate_addresses)
            )
        )
        existing = set(result.scalars().all())

        for address, pool, launchpad, dex_id, attrs in candidate_pools:
            if address in existing:
                continue

            pool_address = attrs.get("address", "")
            created_str = attrs.get("pool_created_at", "")
            try:
                created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                created_at = datetime.now(timezone.utc)

            token = LaunchToken(
                address=address,
                pair_address=pool_address,
                launchpad=launchpad,
                dex=dex_id,
                created_at=created_at,
            )
            session.add(token)
            new_count += 1

        if new_count:
            await session.commit()
            logger.info(f"Discovered {new_count} new launchpad token(s)")

    return new_count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_launch_discovery.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/launch/discovery.py backend/tests/test_launch_discovery.py
git commit -m "feat(launch): add GeckoTerminal discovery job"
```

---

## Task 4: DexScreener Enrichment Job

**Files:**
- Create: `backend/app/launch/enrichment.py`
- Test: `backend/tests/test_launch_enrichment.py`

- [ ] **Step 1: Write failing tests for enrichment**

```python
# backend/tests/test_launch_enrichment.py
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
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
    mock_response = AsyncMock()
    mock_response.json.return_value = _make_dexscreener_response(
        "TokenA", mcap=50000, volume_h1=2000, buys=100, sells=50, liquidity=5000,
    )
    mock_response.raise_for_status = lambda: None
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
    mock_response = AsyncMock()
    mock_response.json.return_value = _make_dexscreener_response(
        "TokenC", mcap=50000, volume_h1=1000, buys=50, sells=30, liquidity=3000,
    )
    mock_response.raise_for_status = lambda: None
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
    mock_response = AsyncMock()
    mock_response.json.return_value = _make_dexscreener_response(
        "TokenD", mcap=100, volume_h1=50, buys=2, sells=1, liquidity=50,
    )
    mock_response.raise_for_status = lambda: None
    mock_http.get.return_value = mock_response

    from app.launch.enrichment import enrich_tracked_tokens
    await enrich_tracked_tokens(engine, mock_http)

    async with get_session(engine) as session:
        result = await session.execute(select(LaunchToken).where(LaunchToken.address == "TokenD"))
        token = result.scalar_one()
        assert token.is_alive is False  # volume_h1=50 < $100
    await engine.dispose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_launch_enrichment.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement enrichment job**

```python
# backend/app/launch/enrichment.py
"""DexScreener enrichment: batch-updates tracked tokens with performance data."""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.database import get_session
from app.launch.models import LaunchToken

logger = logging.getLogger(__name__)

DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/tokens/v1/solana"
BATCH_SIZE = 30
ALIVE_VOLUME_THRESHOLD = 100.0  # $100/hr minimum


async def enrich_tracked_tokens(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch DexScreener data for all non-complete tokens and update their metrics.

    Returns the number of tokens updated.
    """
    now = datetime.now(timezone.utc)

    # Load addresses of tokens that still need updates (avoid loading full objects just to get addresses)
    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchToken.address).where(LaunchToken.checkpoint_complete == False)  # noqa: E712
        )
        addresses = list(result.scalars().all())

    if not addresses:
        return 0

    # Batch fetch from DexScreener
    all_pairs = []
    for i in range(0, len(addresses), BATCH_SIZE):
        batch = addresses[i : i + BATCH_SIZE]
        url = f"{DEXSCREENER_TOKENS_URL}/{','.join(batch)}"
        try:
            resp = await http_client.get(url, timeout=15.0)
            resp.raise_for_status()
            pairs = resp.json()
            if isinstance(pairs, list):
                all_pairs.extend(pairs)
        except Exception as e:
            logger.warning(f"DexScreener enrichment batch failed: {e}")
            continue

    if not all_pairs:
        return 0

    # Index pairs by base token address (take first pair per token)
    pair_by_token: dict[str, dict] = {}
    for pair in all_pairs:
        addr = pair.get("baseToken", {}).get("address", "")
        if addr and addr not in pair_by_token:
            pair_by_token[addr] = pair

    updated = 0
    async with get_session(engine) as session:
        # Re-load tokens within this session for updates
        result = await session.execute(
            select(LaunchToken).where(LaunchToken.checkpoint_complete == False)  # noqa: E712
        )
        tokens_to_update = result.scalars().all()

        for token in tokens_to_update:
            pair = pair_by_token.get(token.address)
            if not pair:
                continue

            age = now - token.created_at
            mcap = pair.get("marketCap") or 0
            volume = pair.get("volume", {})
            txns = pair.get("txns", {})
            liq = pair.get("liquidity", {})

            vol_h1 = volume.get("h1", 0) or 0
            vol_h24 = volume.get("h24", 0) or 0

            buys_h1 = txns.get("h1", {}).get("buys", 0) or 0
            sells_h1 = txns.get("h1", {}).get("sells", 0) or 0
            buys_h24 = txns.get("h24", {}).get("buys", 0) or 0
            sells_h24 = txns.get("h24", {}).get("sells", 0) or 0

            liquidity_usd = liq.get("usd", 0) or 0

            # Update current data
            token.mcap_current = mcap
            token.liquidity_usd = liquidity_usd
            token.is_alive = vol_h1 >= ALIVE_VOLUME_THRESHOLD
            token.last_updated = now

            # Track peak mcap within checkpoint windows
            # IMPORTANT: Save old peak BEFORE updating so we can detect new peaks
            if age <= timedelta(hours=1):
                old_peak_1h = token.mcap_peak_1h or 0
                token.mcap_peak_1h = max(old_peak_1h, mcap)
            elif token.mcap_peak_1h is None:
                token.mcap_peak_1h = mcap

            if age <= timedelta(hours=24):
                old_peak_24h = token.mcap_peak_24h or 0
                token.mcap_peak_24h = max(old_peak_24h, mcap)
                # Update time_to_peak only if this is a NEW peak
                if mcap > old_peak_24h:
                    token.time_to_peak_minutes = int(age.total_seconds() / 60)
            elif token.mcap_peak_24h is None:
                token.mcap_peak_24h = mcap

            if age <= timedelta(days=7):
                old_peak_7d = token.mcap_peak_7d or 0
                token.mcap_peak_7d = max(old_peak_7d, mcap)
            elif token.mcap_peak_7d is None:
                token.mcap_peak_7d = mcap

            # Snapshot checkpoint metrics at the right times
            # NOTE: DexScreener's h1/h24 are rolling windows from "now", not from
            # the token's creation time. These are approximations — the true
            # "first hour volume" would require tracking from creation, but
            # DexScreener doesn't provide that granularity.
            if age >= timedelta(hours=1) and token.volume_1h is None:
                token.volume_1h = vol_h1
                token.buys_1h = buys_h1
                token.sells_1h = sells_h1

            if age >= timedelta(hours=24) and token.volume_24h is None:
                token.volume_24h = vol_h24
                token.buys_24h = buys_h24
                token.sells_24h = sells_h24

            if age >= timedelta(days=7) and token.volume_7d is None:
                # DexScreener has no 7d volume field — use h24 at 7d mark as proxy
                token.volume_7d = volume.get("h24", 0)
                token.checkpoint_complete = True

            updated += 1

        if updated:
            await session.commit()
            logger.info(f"Enriched {updated} token(s) via DexScreener")

    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_launch_enrichment.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/launch/enrichment.py backend/tests/test_launch_enrichment.py
git commit -m "feat(launch): add DexScreener enrichment job"
```

---

## Task 5: Aggregation and Cleanup Jobs

**Files:**
- Create: `backend/app/launch/aggregation.py`
- Test: `backend/tests/test_launch_aggregation.py`

- [ ] **Step 1: Write failing tests for aggregation**

```python
# backend/tests/test_launch_aggregation.py
import pytest
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from app.database import init_db, get_session
from app.launch.models import LaunchToken, LaunchDailyStats

# NOTE: LaunchDailyStats is needed for both aggregation tests AND cleanup tests
# (cleanup verifies aggregation exists before deleting)


@pytest.mark.asyncio
async def test_aggregate_computes_daily_stats():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    d = date(2026, 3, 27)

    async with get_session(engine) as session:
        # Add 3 tokens from same day, same launchpad
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

    assert count >= 1  # At least one row for "pumpfun"
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
        # Old complete token (should be deleted — has aggregation row)
        session.add(LaunchToken(
            address="OldToken", pair_address="OldPair",
            launchpad="pumpfun", dex="pumpswap",
            created_at=now - timedelta(days=100),
            checkpoint_complete=True,
        ))
        # Aggregation row for old_date (required for cleanup to proceed)
        session.add(LaunchDailyStats(
            date=old_date, launchpad="all",
            tokens_created=100, tokens_migrated=5, migration_rate=0.05, total_launches=5,
        ))
        # Recent complete token (should be kept — too recent)
        session.add(LaunchToken(
            address="RecentToken", pair_address="RecentPair",
            launchpad="pumpfun", dex="pumpswap",
            created_at=now - timedelta(days=30),
            checkpoint_complete=True,
        ))
        # Old incomplete token (should be kept — not complete)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_launch_aggregation.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement aggregation and cleanup**

```python
# backend/app/launch/aggregation.py
"""Daily aggregation of launch token data and old token cleanup."""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from sqlalchemy import select, delete

from app.database import get_session
from app.launch.models import LaunchToken, LaunchDailyStats

logger = logging.getLogger(__name__)

RETENTION_DAYS = 90


async def aggregate_launch_stats(engine) -> int:
    """Compute daily stats from launch_tokens and upsert into launch_daily_stats.

    Returns number of rows upserted.
    """
    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchToken).where(LaunchToken.checkpoint_complete == True)  # noqa: E712
        )
        tokens = result.scalars().all()

    if not tokens:
        return 0

    # Group by (date, launchpad)
    groups: dict[tuple[date, str], list[LaunchToken]] = defaultdict(list)
    all_by_date: dict[date, list[LaunchToken]] = defaultdict(list)

    for token in tokens:
        d = token.created_at.date()
        groups[(d, token.launchpad)].append(token)
        all_by_date[d].append(token)

    # Also add "all" aggregate per date
    for d, toks in all_by_date.items():
        groups[(d, "all")] = toks

    count = 0
    async with get_session(engine) as session:
        for (d, launchpad), toks in groups.items():
            stats = _compute_stats(toks)

            # Upsert
            result = await session.execute(
                select(LaunchDailyStats).where(
                    LaunchDailyStats.date == d,
                    LaunchDailyStats.launchpad == launchpad,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                for key, value in stats.items():
                    setattr(existing, key, value)
            else:
                row = LaunchDailyStats(date=d, launchpad=launchpad, **stats)
                session.add(row)
            count += 1

        await session.commit()

    if count:
        logger.info(f"Aggregated {count} daily stat row(s)")
    return count


def _compute_stats(tokens: list[LaunchToken]) -> dict:
    """Compute aggregate stats for a group of tokens."""
    n = len(tokens)
    peaks_1h = [t.mcap_peak_1h for t in tokens if t.mcap_peak_1h is not None]
    peaks_24h = [t.mcap_peak_24h for t in tokens if t.mcap_peak_24h is not None]
    peaks_7d = [t.mcap_peak_7d for t in tokens if t.mcap_peak_7d is not None]
    times_to_peak = [t.time_to_peak_minutes for t in tokens if t.time_to_peak_minutes is not None]

    alive_1h = sum(1 for t in tokens if t.volume_1h is not None and t.volume_1h >= 100)
    alive_24h = sum(1 for t in tokens if t.volume_24h is not None and t.volume_24h >= 100)
    alive_7d = sum(1 for t in tokens if t.is_alive)
    with_1h = sum(1 for t in tokens if t.volume_1h is not None)
    with_24h = sum(1 for t in tokens if t.volume_24h is not None)

    buy_sell_ratios = []
    for t in tokens:
        if t.buys_1h is not None and t.sells_1h and t.sells_1h > 0:
            buy_sell_ratios.append(t.buys_1h / t.sells_1h)

    volumes = [t.volume_1h for t in tokens if t.volume_1h is not None]

    return {
        "tokens_created": n,  # placeholder — real count comes from RPC
        "tokens_migrated": n,
        "migration_rate": 0.0,  # placeholder — needs RPC denominator
        "median_peak_mcap_1h": median(peaks_1h) if peaks_1h else None,
        "median_peak_mcap_24h": median(peaks_24h) if peaks_24h else None,
        "median_peak_mcap_7d": median(peaks_7d) if peaks_7d else None,
        "median_time_to_peak": median(times_to_peak) if times_to_peak else None,
        "survival_rate_1h": (alive_1h / with_1h * 100) if with_1h else None,
        "survival_rate_24h": (alive_24h / with_24h * 100) if with_24h else None,
        "survival_rate_7d": (alive_7d / n * 100) if n else None,
        "avg_buy_sell_ratio_1h": (sum(buy_sell_ratios) / len(buy_sell_ratios)) if buy_sell_ratios else None,
        "total_launches": n,
        "total_volume": sum(volumes) if volumes else None,
    }


async def cleanup_old_tokens(engine) -> int:
    """Delete launch_tokens rows that are complete, older than RETENTION_DAYS,
    and whose data has been aggregated into launch_daily_stats.

    Returns number of rows deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

    async with get_session(engine) as session:
        # Find candidate tokens for deletion
        result = await session.execute(
            select(LaunchToken).where(
                LaunchToken.checkpoint_complete == True,  # noqa: E712
                LaunchToken.created_at < cutoff,
            )
        )
        candidates = result.scalars().all()
        if not candidates:
            return 0

        # Only delete tokens whose date has a corresponding aggregation row
        dates_to_check = {t.created_at.date() for t in candidates}
        agg_result = await session.execute(
            select(LaunchDailyStats.date).where(
                LaunchDailyStats.date.in_(dates_to_check),
                LaunchDailyStats.launchpad == "all",
            )
        )
        aggregated_dates = set(agg_result.scalars().all())

        to_delete = [t for t in candidates if t.created_at.date() in aggregated_dates]
        for token in to_delete:
            await session.delete(token)

        deleted = len(to_delete)
        if deleted:
            await session.commit()
            logger.info(f"Cleaned up {deleted} old launch token(s)")
    return deleted
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_launch_aggregation.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/launch/aggregation.py backend/tests/test_launch_aggregation.py
git commit -m "feat(launch): add daily aggregation and token cleanup jobs"
```

---

## Task 6: API Endpoints

**Files:**
- Create: `backend/app/routers/launch.py`
- Test: `backend/tests/test_launch_api.py`

- [ ] **Step 1: Write failing tests for the overview endpoint**

```python
# backend/tests/test_launch_api.py
import pytest
from datetime import date, datetime, timezone
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.database import init_db, get_session
from app.launch.models import LaunchDailyStats


@pytest.fixture
async def app_with_data():
    """Create a FastAPI app with launch router and seed data."""
    engine = await init_db("sqlite+aiosqlite:///:memory:")

    from app.routers.launch import router, set_engine
    set_engine(engine)

    app = FastAPI()
    app.include_router(router)

    # Seed daily stats
    async with get_session(engine) as session:
        for i in range(7):
            d = date(2026, 3, 22 + i)
            session.add(LaunchDailyStats(
                date=d, launchpad="all",
                tokens_created=1000 + i * 100, tokens_migrated=30 + i * 5,
                migration_rate=0.03 + i * 0.005,
                median_peak_mcap_1h=50000 + i * 5000,
                median_peak_mcap_24h=80000 + i * 8000,
                median_time_to_peak=45.0 + i * 2,
                survival_rate_1h=80.0 - i,
                survival_rate_24h=40.0 - i,
                survival_rate_7d=10.0 - i * 0.5,
                avg_buy_sell_ratio_1h=1.5 + i * 0.1,
                total_launches=30 + i * 5,
                total_volume=500000 + i * 50000,
            ))
            # Also add per-launchpad rows
            session.add(LaunchDailyStats(
                date=d, launchpad="pumpfun",
                tokens_created=800 + i * 80, tokens_migrated=20 + i * 3,
                migration_rate=0.025, total_launches=20 + i * 3,
                median_peak_mcap_1h=40000, median_peak_mcap_24h=60000,
            ))
        await session.commit()

    yield app
    await engine.dispose()


@pytest.mark.asyncio
async def test_overview_endpoint(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/launch/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        # Should have 8 metrics
        assert len(data["metrics"]) == 8
        # Each metric should have current, trend, chart
        for m in data["metrics"]:
            assert "name" in m
            assert "current" in m
            assert "trend" in m
            assert "chart" in m


@pytest.mark.asyncio
async def test_migration_rate_endpoint(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/launch/migration-rate?range=7d")
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data
        assert "chart" in data
        assert "breakdown" in data
        assert "last_updated" in data


@pytest.mark.asyncio
async def test_range_filter(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_7d = await client.get("/api/launch/launches?range=7d")
        resp_30d = await client.get("/api/launch/launches?range=30d")
        assert resp_7d.status_code == 200
        assert resp_30d.status_code == 200


@pytest.mark.asyncio
async def test_invalid_range(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/launch/overview?range=invalid")
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_launch_api.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement the launch router**

```python
# backend/app/routers/launch.py
"""API endpoints for the Launch Environment Monitor."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.database import get_session
from app.launch.models import LaunchDailyStats

router = APIRouter(prefix="/api/launch", tags=["launch"])

_engine = None

RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def set_engine(engine):
    global _engine
    _engine = engine


def _get_range_cutoff(range_param: str) -> date:
    if range_param not in RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Invalid range: {range_param}. Valid: 7d, 30d, 90d")
    return date.today() - timedelta(days=RANGE_DAYS[range_param])


def _compute_trend(chart: list[dict]) -> str:
    """Determine trend from last 7 chart points."""
    if len(chart) < 2:
        return "flat"
    recent = [p["value"] for p in chart[-7:] if p["value"] is not None]
    if len(recent) < 2:
        return "flat"
    if recent[-1] > recent[0] * 1.02:
        return "up"
    elif recent[-1] < recent[0] * 0.98:
        return "down"
    return "flat"


async def _get_stats(range_param: str, launchpad: str = "all") -> list[LaunchDailyStats]:
    cutoff = _get_range_cutoff(range_param)
    async with get_session(_engine) as session:
        result = await session.execute(
            select(LaunchDailyStats)
            .where(LaunchDailyStats.launchpad == launchpad)
            .where(LaunchDailyStats.date >= cutoff)
            .order_by(LaunchDailyStats.date)
        )
        return result.scalars().all()


async def _get_breakdown(range_param: str) -> dict[str, list[LaunchDailyStats]]:
    cutoff = _get_range_cutoff(range_param)
    async with get_session(_engine) as session:
        result = await session.execute(
            select(LaunchDailyStats)
            .where(LaunchDailyStats.launchpad != "all")
            .where(LaunchDailyStats.date >= cutoff)
            .order_by(LaunchDailyStats.date)
        )
        rows = result.scalars().all()
    breakdown: dict[str, list[LaunchDailyStats]] = {}
    for row in rows:
        breakdown.setdefault(row.launchpad, []).append(row)
    return breakdown


async def _get_last_enrichment_time() -> str:
    """Get the most recent token update time as the real 'last_updated' indicator."""
    async with get_session(_engine) as session:
        from app.launch.models import LaunchToken
        result = await session.execute(
            select(LaunchToken.last_updated)
            .order_by(LaunchToken.last_updated.desc())
            .limit(1)
        )
        ts = result.scalar_one_or_none()
        return ts.isoformat() if ts else datetime.now(timezone.utc).isoformat()


def _metric_response(name: str, stats: list, field: str, last_updated: str, breakdown_field: str | None = None, breakdown_data: dict | None = None):
    chart = [{"date": str(s.date), "value": getattr(s, field)} for s in stats]
    current = getattr(stats[-1], field) if stats else None

    resp = {
        "name": name,
        "current": current,
        "trend": _compute_trend(chart),
        "last_updated": last_updated,
        "chart": chart,
    }

    if breakdown_data and breakdown_field:
        bd = {}
        for lp, lp_stats in breakdown_data.items():
            if lp_stats:
                bd[lp] = getattr(lp_stats[-1], breakdown_field)
        resp["breakdown"] = bd
    elif breakdown_data:
        bd = {}
        for lp, lp_stats in breakdown_data.items():
            if lp_stats:
                bd[lp] = getattr(lp_stats[-1], field)
        resp["breakdown"] = bd

    return resp


@router.get("/overview")
async def get_overview(range: str = Query("30d")):
    if range not in RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Invalid range: {range}")
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()

    metrics = [
        _metric_response("Migration Rate", stats, "migration_rate", lu),
        _metric_response("Median Peak Mcap (1h)", stats, "median_peak_mcap_1h", lu),
        _metric_response("Time to Peak", stats, "median_time_to_peak", lu),
        _metric_response("Survival Rate (24h)", stats, "survival_rate_24h", lu),
        _metric_response("Buy/Sell Ratio", stats, "avg_buy_sell_ratio_1h", lu),
        _metric_response("Daily Launches", stats, "total_launches", lu),
        _metric_response("Volume", stats, "total_volume", lu),
        _metric_response("Capital Flow", stats, "total_volume", lu),  # Placeholder — uses DefiLlama data later
    ]

    return {"metrics": metrics, "last_updated": lu}


@router.get("/migration-rate")
async def get_migration_rate(range: str = Query("30d")):
    stats = await _get_stats(range)
    breakdown = await _get_breakdown(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Migration Rate", stats, "migration_rate", lu, "migration_rate", breakdown)


@router.get("/peak-mcap")
async def get_peak_mcap(range: str = Query("30d")):
    stats = await _get_stats(range)
    breakdown = await _get_breakdown(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Median Peak Mcap", stats, "median_peak_mcap_1h", lu, "median_peak_mcap_1h", breakdown)


@router.get("/time-to-peak")
async def get_time_to_peak(range: str = Query("30d")):
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Time to Peak", stats, "median_time_to_peak", lu)


@router.get("/survival")
async def get_survival(range: str = Query("30d")):
    stats = await _get_stats(range)
    breakdown = await _get_breakdown(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Survival Rate", stats, "survival_rate_24h", lu, "survival_rate_24h", breakdown)


@router.get("/buy-sell")
async def get_buy_sell(range: str = Query("30d")):
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Buy/Sell Ratio", stats, "avg_buy_sell_ratio_1h", lu)


@router.get("/launches")
async def get_launches(range: str = Query("30d")):
    stats = await _get_stats(range)
    breakdown = await _get_breakdown(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Daily Launches", stats, "total_launches", lu, "total_launches", breakdown)


@router.get("/volume")
async def get_volume(range: str = Query("30d")):
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("On-Chain Volume", stats, "total_volume", lu)


@router.get("/capital-flow")
async def get_capital_flow(range: str = Query("30d")):
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Capital Flow", stats, "total_volume", lu)  # Placeholder
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_launch_api.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/launch.py backend/tests/test_launch_api.py
git commit -m "feat(launch): add API router with 9 endpoints"
```

---

## Task 7: Config and Main.py Wiring

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add config settings for launch fetch intervals**

Add to `backend/app/config.py` inside the `Settings` class, after the existing fetch intervals:

```python
    # Launch monitor intervals (seconds)
    fetch_interval_launch_discovery: int = 120   # 2 min
    fetch_interval_launch_enrichment: int = 120  # 2 min
```

- [ ] **Step 2: Wire up launch jobs and router in main.py**

Add imports at the top of `backend/app/main.py`:

```python
from app.routers.launch import router as launch_router, set_engine as set_launch_engine
from app.launch.discovery import discover_new_launches
from app.launch.enrichment import enrich_tracked_tokens
from app.launch.aggregation import aggregate_launch_stats, cleanup_old_tokens
```

Add after the existing `set_ecosystem_engine(db_engine)` line in the `lifespan` function:

```python
    # Launch monitor
    set_launch_engine(db_engine)
```

Add after the existing `scheduler.add_job(compute_today_score, ...)` block:

```python
    # Launch monitor jobs
    scheduler.add_job(
        discover_new_launches,
        args=[db_engine, http_client],
        trigger=IntervalTrigger(seconds=settings.fetch_interval_launch_discovery),
        id="discover_new_launches",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        enrich_tracked_tokens,
        args=[db_engine, http_client],
        trigger=IntervalTrigger(seconds=settings.fetch_interval_launch_enrichment),
        id="enrich_tracked_tokens",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        aggregate_launch_stats,
        args=[db_engine],
        trigger=IntervalTrigger(seconds=86400),  # Daily
        id="aggregate_launch_stats",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        cleanup_old_tokens,
        args=[db_engine],
        trigger=IntervalTrigger(seconds=604800),  # Weekly
        id="cleanup_old_tokens",
        replace_existing=True,
        max_instances=1,
    )
```

Add the router registration after the existing `app.include_router(ecosystem_router)`:

```python
app.include_router(launch_router)
```

- [ ] **Step 3: Verify the app starts without errors**

Run: `cd backend && python -c "from app.main import app; print('OK')"`
Expected: prints "OK" without import errors

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/app/main.py
git commit -m "feat(launch): wire up discovery, enrichment, aggregation jobs and API router"
```

---

## Task 8: Frontend Types and API Layer

**Files:**
- Create: `frontend/src/types/launch.ts`
- Create: `frontend/src/api/launch.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/types/launch.ts

export interface LaunchChartPoint {
  date: string;
  value: number | null;
}

export interface LaunchMetricData {
  name: string;
  current: number | null;
  trend: "up" | "down" | "flat";
  last_updated: string;
  chart: LaunchChartPoint[];
  breakdown?: Record<string, number | null>;
}

export interface LaunchOverviewData {
  metrics: LaunchMetricData[];
  last_updated: string;
}

export type LaunchRange = "7d" | "30d" | "90d";

// Metric slugs used in URLs
export type LaunchMetricSlug =
  | "migration-rate"
  | "peak-mcap"
  | "time-to-peak"
  | "survival"
  | "buy-sell"
  | "launches"
  | "volume"
  | "capital-flow";
```

- [ ] **Step 2: Create API fetch functions**

```typescript
// frontend/src/api/launch.ts
import { apiFetch } from "./client";
import type { LaunchOverviewData, LaunchMetricData, LaunchRange } from "../types/launch";

export function fetchLaunchOverview(range: LaunchRange = "30d"): Promise<LaunchOverviewData> {
  return apiFetch<LaunchOverviewData>(`/launch/overview?range=${range}`);
}

export function fetchLaunchMetric(
  slug: string,
  range: LaunchRange = "30d"
): Promise<LaunchMetricData> {
  return apiFetch<LaunchMetricData>(`/launch/${slug}?range=${range}`);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/launch.ts frontend/src/api/launch.ts
git commit -m "feat(launch): add frontend types and API layer"
```

---

## Task 9: LaunchMetricCard Component

**Files:**
- Create: `frontend/src/components/launch/LaunchMetricCard.tsx`

- [ ] **Step 1: Create the metric card component**

```tsx
// frontend/src/components/launch/LaunchMetricCard.tsx
import { useNavigate } from "react-router-dom";
import type { LaunchMetricData, LaunchMetricSlug } from "../../types/launch";

// Map metric names to URL slugs
const METRIC_SLUGS: Record<string, LaunchMetricSlug> = {
  "Migration Rate": "migration-rate",
  "Median Peak Mcap (1h)": "peak-mcap",
  "Time to Peak": "time-to-peak",
  "Survival Rate (24h)": "survival",
  "Buy/Sell Ratio": "buy-sell",
  "Daily Launches": "launches",
  "Volume": "volume",
  "Capital Flow": "capital-flow",
};

function formatValue(name: string, value: number | null): string {
  if (value === null || value === undefined) return "—";
  if (name.includes("Rate") || name.includes("Migration")) return `${value.toFixed(1)}%`;
  if (name.includes("Mcap") || name.includes("Volume") || name.includes("Capital")) {
    if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
    return `$${value.toFixed(0)}`;
  }
  if (name.includes("Time")) return `${value.toFixed(0)}min`;
  if (name.includes("Ratio")) return value.toFixed(2);
  return value.toLocaleString();
}

function Sparkline({ data }: { data: { value: number | null }[] }) {
  const values = data.map((d) => d.value).filter((v): v is number => v !== null);
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 120;
  const h = 32;

  const points = values
    .slice(-30)
    .map((v, i, arr) => {
      const x = (i / (arr.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={w} height={h} className="mt-2">
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        className="text-terminal-accent"
      />
    </svg>
  );
}

const TREND_ARROWS = { up: "▲", down: "▼", flat: "—" };
const TREND_COLORS = {
  up: "text-terminal-green",
  down: "text-terminal-red",
  flat: "text-terminal-muted",
};

export default function LaunchMetricCard({ metric }: { metric: LaunchMetricData }) {
  const navigate = useNavigate();
  const slug = METRIC_SLUGS[metric.name];

  return (
    <button
      onClick={() => slug && navigate(`/launch/${slug}`)}
      className="bg-terminal-card border border-terminal-border rounded p-4 text-left hover:border-terminal-accent/40 transition-colors w-full"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs text-terminal-muted uppercase tracking-wide">
          {metric.name}
        </span>
        <span className={`text-xs ${TREND_COLORS[metric.trend]}`}>
          {TREND_ARROWS[metric.trend]}
        </span>
      </div>
      <div className="text-xl font-bold text-terminal-text mt-1">
        {metric.current !== null ? formatValue(metric.name, metric.current) : (
          <span className="text-terminal-muted text-sm">Collecting data...</span>
        )}
      </div>
      <Sparkline data={metric.chart} />
    </button>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/launch/LaunchMetricCard.tsx
git commit -m "feat(launch): add LaunchMetricCard component with sparkline"
```

---

## Task 10: LaunchDashboard Page

**Files:**
- Create: `frontend/src/pages/LaunchDashboard.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create the dashboard page**

```tsx
// frontend/src/pages/LaunchDashboard.tsx
import PageLayout from "../components/layout/PageLayout";
import LaunchMetricCard from "../components/launch/LaunchMetricCard";
import { useApiPolling } from "../hooks/useApiPolling";
import type { LaunchOverviewData } from "../types/launch";

export default function LaunchDashboard() {
  // Uses useApiPolling with the path that apiFetch will prefix with /api
  const { data, loading, error } = useApiPolling<LaunchOverviewData>(
    "/launch/overview?range=30d",
    60000, // Poll every 60s
  );

  return (
    <PageLayout title="Launch Monitor">
      {loading && !data && (
        <div className="text-terminal-muted text-center py-16">
          Loading launch data...
        </div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}

      {data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {data.metrics.map((metric) => (
            <LaunchMetricCard key={metric.name} metric={metric} />
          ))}
        </div>
      )}

      {data && data.metrics.every((m) => m.current === null) && (
        <div className="text-terminal-muted text-center py-8 text-sm">
          Data collection has started. Metrics will appear as data accumulates.
        </div>
      )}
    </PageLayout>
  );
}
```

- [ ] **Step 2: Add routes to App.tsx**

Add import at top of `frontend/src/App.tsx`:

```typescript
import LaunchDashboard from "./pages/LaunchDashboard";
import LaunchDetail from "./pages/LaunchDetail";
```

Add routes inside the `<Routes>` block, after the `/pulse` route:

```tsx
          <Route path="/launch" element={<LaunchDashboard />} />
          <Route path="/launch/:metric" element={<LaunchDetail />} />
```

- [ ] **Step 3: Verify the page renders**

Run the frontend dev server and navigate to `http://localhost:5173/launch`. Should show "Loading launch data..." or the grid of cards if the backend is also running.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LaunchDashboard.tsx frontend/src/App.tsx
git commit -m "feat(launch): add LaunchDashboard page and routes"
```

---

## Task 11: LaunchDetail Page and LaunchBreakdownTable

**Files:**
- Create: `frontend/src/pages/LaunchDetail.tsx`
- Create: `frontend/src/components/launch/LaunchBreakdownTable.tsx`

- [ ] **Step 1: Create the breakdown table component**

```tsx
// frontend/src/components/launch/LaunchBreakdownTable.tsx

interface Props {
  breakdown: Record<string, number | null>;
  formatValue?: (v: number | null) => string;
}

function defaultFormat(v: number | null): string {
  if (v === null || v === undefined) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  if (v < 1 && v > 0) return `${(v * 100).toFixed(1)}%`;
  return v.toLocaleString();
}

export default function LaunchBreakdownTable({ breakdown, formatValue = defaultFormat }: Props) {
  const entries = Object.entries(breakdown).sort(
    (a, b) => (b[1] ?? 0) - (a[1] ?? 0)
  );

  if (entries.length === 0) return null;

  return (
    <div className="mt-6">
      <h3 className="text-xs text-terminal-muted uppercase tracking-wide mb-3">
        By Launchpad
      </h3>
      <div className="bg-terminal-card border border-terminal-border rounded">
        {entries.map(([name, value]) => (
          <div
            key={name}
            className="flex items-center justify-between px-4 py-2 border-b border-terminal-border last:border-b-0"
          >
            <span className="text-sm text-terminal-text capitalize">{name}</span>
            <span className="text-sm font-mono text-terminal-accent">
              {formatValue(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create the detail page**

```tsx
// frontend/src/pages/LaunchDetail.tsx
import { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import LaunchBreakdownTable from "../components/launch/LaunchBreakdownTable";
import { useApiPolling } from "../hooks/useApiPolling";
import type { LaunchMetricData, LaunchRange } from "../types/launch";

const RANGES: LaunchRange[] = ["7d", "30d", "90d"];

const METRIC_TITLES: Record<string, string> = {
  "migration-rate": "Migration Rate",
  "peak-mcap": "Median Peak Market Cap",
  "time-to-peak": "Time to Peak",
  survival: "Survival Rate",
  "buy-sell": "Buy/Sell Ratio",
  launches: "Daily Launches",
  volume: "On-Chain Volume",
  "capital-flow": "Capital Flow",
};

function SimpleChart({ data }: { data: { date: string; value: number | null }[] }) {
  const values = data.map((d) => d.value).filter((v): v is number => v !== null);
  if (values.length < 2) return <div className="text-terminal-muted py-8 text-center">Insufficient data</div>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 800;
  const h = 300;
  const padding = 40;

  const points = data
    .map((d, i) => {
      if (d.value === null) return null;
      const x = padding + (i / (data.length - 1)) * (w - padding * 2);
      const y = padding + (1 - (d.value - min) / range) * (h - padding * 2);
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 300 }}>
      <polyline
        points={points}
        fill="none"
        stroke="var(--color-terminal-accent)"
        strokeWidth={2}
      />
    </svg>
  );
}

export default function LaunchDetail() {
  const { metric } = useParams<{ metric: string }>();
  const navigate = useNavigate();
  const [range, setRange] = useState<LaunchRange>("30d");

  const { data, loading, error } = useApiPolling<LaunchMetricData>(
    `/launch/${metric}?range=${range}`,
    60000,
  );

  const title = metric ? METRIC_TITLES[metric] || metric : "Metric";

  return (
    <PageLayout title={title}>
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => navigate("/launch")}
          className="text-sm text-terminal-muted hover:text-terminal-text"
        >
          ← Back
        </button>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1 text-xs rounded ${
                range === r
                  ? "bg-terminal-accent/20 text-terminal-accent"
                  : "text-terminal-muted hover:text-terminal-text"
              }`}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {data && (
        <>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl font-bold text-terminal-text">
              {data.current !== null ? data.current.toLocaleString() : "—"}
            </span>
            <span
              className={`text-sm ${
                data.trend === "up"
                  ? "text-terminal-green"
                  : data.trend === "down"
                    ? "text-terminal-red"
                    : "text-terminal-muted"
              }`}
            >
              {data.trend === "up" ? "▲" : data.trend === "down" ? "▼" : "—"}
            </span>
          </div>

          <div className="bg-terminal-card border border-terminal-border rounded p-4">
            <SimpleChart data={data.chart} />
          </div>

          {data.breakdown && (
            <LaunchBreakdownTable breakdown={data.breakdown} />
          )}
        </>
      )}

      {loading && !data && (
        <div className="text-terminal-muted text-center py-16">Loading...</div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}
    </PageLayout>
  );
}
```

- [ ] **Step 3: Verify detail page renders**

Navigate to `http://localhost:5173/launch/migration-rate`. Should show the detail layout with back button, range selector, chart, and breakdown table.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LaunchDetail.tsx frontend/src/components/launch/LaunchBreakdownTable.tsx
git commit -m "feat(launch): add LaunchDetail page and LaunchBreakdownTable"
```

---

## Task 12: Run All Tests and Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass including the new launch tests and all existing tests

- [ ] **Step 2: Verify backend starts cleanly**

Run: `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
Expected: App starts, launch jobs are scheduled, `/api/launch/overview` returns data (may be empty during cold start)

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No TypeScript errors

- [ ] **Step 4: Manual smoke test**

1. Open `http://localhost:5173/launch` — should see 8 metric cards (may show "Collecting data..." initially)
2. Click a card — should navigate to detail page with chart and breakdown
3. Change range selector — chart should update
4. Click "← Back" — should return to dashboard

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(launch): complete Launch Environment Monitor implementation"
```
