# Pulse Redesign: Data-Driven Health Score — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Pulse page with a price-focused dashboard centered on a SOL candlestick chart with a data-driven health score computed from historically correlated factors.

**Architecture:** Backend ingests historical data (SOL CSV, Fear & Greed API, DeFi Llama TVL/DEX/stablecoin), runs Pearson correlation analysis against SOL forward returns to derive factor weights, backfills daily scores, and serves three new API endpoints (`/chart`, `/correlations`, `/ecosystem`). Frontend replaces Recharts with TradingView lightweight-charts for a candlestick chart with score-based green/red background gradient and a synced health score line below.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy async, numpy (new), lightweight-charts (new), React 18, Tailwind CSS 4

**Spec:** `docs/superpowers/specs/2026-03-27-pulse-redesign-data-driven-score.md`

---

## File Structure

### Backend — New Files
- `backend/app/ingestion/__init__.py` — Package init
- `backend/app/ingestion/sol_csv.py` — SOL OHLCV CSV parser + DB writer
- `backend/app/ingestion/historical_fng.py` — Fear & Greed full history fetcher
- `backend/app/ingestion/historical_defillama.py` — DeFi Llama TVL, DEX volume, stablecoin history fetchers
- `backend/app/ingestion/runner.py` — Orchestrates backfill: calls all ingestors, checks if already done
- `backend/app/analysis/__init__.py` — Package init (already exists from Phase 1 but verify)
- `backend/app/analysis/correlation.py` — Pearson correlation engine with multi-lag analysis + weight derivation
- `backend/app/analysis/score_backfill.py` — Computes historical daily scores using rolling z-scores
- `backend/app/routers/pulse_chart.py` — `/api/pulse/chart?range=30d` endpoint
- `backend/app/routers/pulse_correlations.py` — `/api/pulse/correlations` endpoint
- `backend/app/routers/pulse_ecosystem.py` — `/api/pulse/ecosystem` endpoint
- `backend/tests/test_sol_csv.py` — Tests for CSV ingestion
- `backend/tests/test_historical_fng.py` — Tests for Fear & Greed history
- `backend/tests/test_historical_defillama.py` — Tests for DeFi Llama history
- `backend/tests/test_correlation.py` — Tests for correlation engine
- `backend/tests/test_score_backfill.py` — Tests for score backfill
- `backend/tests/test_pulse_chart.py` — Tests for chart endpoint
- `backend/tests/test_pulse_correlations.py` — Tests for correlations endpoint
- `backend/tests/test_pulse_ecosystem.py` — Tests for ecosystem endpoint

### Backend — Modified Files
- `backend/app/database.py` — Add `DailyScore` and `HistoricalData` models
- `backend/app/main.py` — Replace pulse_router with new routers, add ingestion to lifespan
- `backend/requirements.txt` — Add `numpy`

### Frontend — New Files
- `frontend/src/components/charts/CandlestickChart.tsx` — TradingView lightweight-charts candlestick with score-based background
- `frontend/src/components/charts/ScoreLine.tsx` — Synced health score line chart below candlestick
- `frontend/src/components/charts/RangeSelector.tsx` — Time range selector (30D, 90D, 1Y, All)
- `frontend/src/components/charts/EcosystemCard.tsx` — Sparkline card for live supplementary metrics
- `frontend/src/components/charts/ScoredFactors.tsx` — Scored factors display with correlation/weight transparency
- `frontend/src/api/pulse.ts` — New API functions for chart, correlations, ecosystem endpoints
- `frontend/src/types/pulse.ts` — New TypeScript interfaces for redesigned API responses

### Frontend — Modified Files
- `frontend/src/pages/Pulse.tsx` — Complete rewrite
- `frontend/package.json` — Remove recharts, add lightweight-charts

### Frontend — Removed Files
- `frontend/src/components/charts/TimeSeriesChart.tsx` — Replaced by CandlestickChart
- `frontend/src/components/scores/ScoreCard.tsx` — Score now shown as line chart panel
- `frontend/src/components/scores/FactorBreakdown.tsx` — Replaced by ScoredFactors

---

## Task 1: Database Models — DailyScore and HistoricalData Tables

**Files:**
- Modify: `backend/app/database.py:1-49`
- Test: `backend/tests/test_database.py` (extend existing)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_database.py — append to existing file
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_database.py -v -k "daily_score or historical_data"`
Expected: FAIL with `ImportError: cannot import name 'DailyScore'`

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/database.py` after `MetricData` class:

```python
from sqlalchemy import Date, UniqueConstraint


class DailyScore(Base):
    __tablename__ = "daily_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    score: Mapped[float] = mapped_column(Float)
    factors_json: Mapped[str] = mapped_column(Text)
    factors_available: Mapped[int] = mapped_column(Integer)
    factors_total: Mapped[int] = mapped_column(Integer)


class HistoricalData(Base):
    __tablename__ = "historical_data"
    __table_args__ = (
        UniqueConstraint("source", "date", name="uq_source_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Add `from datetime import date` to the imports (alongside existing `datetime`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_database.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py backend/tests/test_database.py
git commit -m "feat: add DailyScore and HistoricalData database models"
```

---

## Task 2: Add numpy Dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add numpy to requirements**

Append to `backend/requirements.txt`:

```
numpy>=1.26,<3
```

- [ ] **Step 2: Install**

Run: `cd backend && pip install numpy`
Expected: Installs successfully

- [ ] **Step 3: Verify import**

Run: `cd backend && python -c "import numpy; print(numpy.__version__)"`
Expected: Prints version number

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add numpy dependency for correlation analysis"
```

---

## Task 3: SOL OHLCV CSV Ingestion

**Files:**
- Create: `backend/app/ingestion/__init__.py`
- Create: `backend/app/ingestion/sol_csv.py`
- Test: `backend/tests/test_sol_csv.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sol_csv.py
import pytest
import tempfile
import os
from datetime import date
from sqlalchemy import select, func
from app.database import init_db, get_session, HistoricalData
from app.ingestion.sol_csv import ingest_sol_csv


@pytest.mark.asyncio
async def test_ingest_sol_csv_parses_correctly():
    csv_content = (
        "time,open,high,low,close,#1\n"
        "1586476800,0.21464622,1.33977149,0.21379166,0.94799898,\n"
        "1586563200,0.94799013,1.06113905,0.76209019,0.78910001,\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        count = await ingest_sol_csv(engine, csv_path)
        assert count == 2

        async with get_session(engine) as session:
            result = await session.execute(
                select(HistoricalData)
                .where(HistoricalData.source == "sol_ohlcv")
                .order_by(HistoricalData.date)
            )
            rows = result.scalars().all()
            assert len(rows) == 2
            # First row: 2020-04-10, close = 0.94799898
            assert rows[0].date == date(2020, 4, 10)
            assert rows[0].value == pytest.approx(0.94799898, rel=1e-5)
        await engine.dispose()
    finally:
        os.unlink(csv_path)


@pytest.mark.asyncio
async def test_ingest_sol_csv_skips_if_already_ingested():
    csv_content = (
        "time,open,high,low,close,#1\n"
        "1586476800,0.21464622,1.33977149,0.21379166,0.94799898,\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        count1 = await ingest_sol_csv(engine, csv_path)
        count2 = await ingest_sol_csv(engine, csv_path)
        assert count1 == 1
        assert count2 == 0  # skipped

        async with get_session(engine) as session:
            result = await session.execute(
                select(func.count()).select_from(HistoricalData).where(HistoricalData.source == "sol_ohlcv")
            )
            assert result.scalar() == 1
        await engine.dispose()
    finally:
        os.unlink(csv_path)


@pytest.mark.asyncio
async def test_ingest_sol_csv_stores_ohlc_metadata():
    csv_content = (
        "time,open,high,low,close,#1\n"
        "1711497600,185.20,192.10,183.00,190.50,\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name
    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        await ingest_sol_csv(engine, csv_path)

        async with get_session(engine) as session:
            result = await session.execute(select(HistoricalData).where(HistoricalData.source == "sol_ohlcv"))
            row = result.scalar_one()
            import json
            meta = json.loads(row.metadata_json)
            assert meta["open"] == pytest.approx(185.20)
            assert meta["high"] == pytest.approx(192.10)
            assert meta["low"] == pytest.approx(183.00)
            assert meta["close"] == pytest.approx(190.50)
        await engine.dispose()
    finally:
        os.unlink(csv_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sol_csv.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ingestion'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/ingestion/__init__.py`:
```python
```

Create `backend/app/ingestion/sol_csv.py`:
```python
# backend/app/ingestion/sol_csv.py
import csv
import json
import logging
from datetime import date, datetime, timezone

from sqlalchemy import select, func

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)

SOURCE = "sol_ohlcv"


async def ingest_sol_csv(engine, csv_path: str) -> int:
    """Import SOL OHLCV data from CSV into historical_data table.

    Returns the number of rows inserted (0 if already ingested).
    """
    # Check if already ingested
    async with get_session(engine) as session:
        result = await session.execute(
            select(func.count()).select_from(HistoricalData).where(HistoricalData.source == SOURCE)
        )
        existing_count = result.scalar()
        if existing_count > 0:
            logger.info(f"SOL OHLCV already ingested ({existing_count} rows), skipping")
            return 0

    rows_to_insert = []
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header
        for row in reader:
            if len(row) < 5:
                continue
            timestamp = int(row[0])
            open_price = float(row[1])
            high = float(row[2])
            low = float(row[3])
            close = float(row[4])
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()

            rows_to_insert.append(HistoricalData(
                source=SOURCE,
                date=dt,
                value=close,
                metadata_json=json.dumps({
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                }),
            ))

    async with get_session(engine) as session:
        session.add_all(rows_to_insert)
        await session.commit()

    logger.info(f"Ingested {len(rows_to_insert)} SOL OHLCV rows")
    return len(rows_to_insert)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sol_csv.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/__init__.py backend/app/ingestion/sol_csv.py backend/tests/test_sol_csv.py
git commit -m "feat: add SOL OHLCV CSV ingestion into historical_data table"
```

---

## Task 4: Fear & Greed Historical Ingestion

**Files:**
- Create: `backend/app/ingestion/historical_fng.py`
- Test: `backend/tests/test_historical_fng.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_historical_fng.py
import pytest
import httpx
import respx
from datetime import date
from sqlalchemy import select, func
from app.database import init_db, get_session, HistoricalData
from app.ingestion.historical_fng import ingest_fear_greed_history

MOCK_FNG_RESPONSE = {
    "data": [
        {"value": "75", "value_classification": "Greed", "timestamp": "1711497600"},
        {"value": "60", "value_classification": "Greed", "timestamp": "1711411200"},
        {"value": "45", "value_classification": "Fear", "timestamp": "1711324800"},
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_ingest_fng_history():
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(200, json=MOCK_FNG_RESPONSE)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count = await ingest_fear_greed_history(engine, client)
    assert count == 3

    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData)
            .where(HistoricalData.source == "fear_greed")
            .order_by(HistoricalData.date)
        )
        rows = result.scalars().all()
        assert len(rows) == 3
        assert rows[2].value == pytest.approx(75.0)
    await engine.dispose()


@pytest.mark.asyncio
@respx.mock
async def test_ingest_fng_skips_if_exists():
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(200, json=MOCK_FNG_RESPONSE)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count1 = await ingest_fear_greed_history(engine, client)
        count2 = await ingest_fear_greed_history(engine, client)
    assert count1 == 3
    assert count2 == 0
    await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_historical_fng.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/ingestion/historical_fng.py
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, func

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)

URL = "https://api.alternative.me/fng/"
SOURCE = "fear_greed"


async def ingest_fear_greed_history(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch full Fear & Greed Index history and store in historical_data.

    Returns number of rows inserted (0 if already ingested).
    """
    async with get_session(engine) as session:
        result = await session.execute(
            select(func.count()).select_from(HistoricalData).where(HistoricalData.source == SOURCE)
        )
        if result.scalar() > 0:
            logger.info("Fear & Greed history already ingested, skipping")
            return 0

    resp = await http_client.get(URL, params={"limit": 0}, timeout=30.0)
    resp.raise_for_status()
    entries = resp.json().get("data", [])

    rows = []
    for entry in entries:
        ts = int(entry.get("timestamp", 0))
        value = float(entry.get("value", 0))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        rows.append(HistoricalData(
            source=SOURCE,
            date=dt,
            value=value,
            metadata_json=None,
        ))

    async with get_session(engine) as session:
        session.add_all(rows)
        await session.commit()

    logger.info(f"Ingested {len(rows)} Fear & Greed history rows")
    return len(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_historical_fng.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/historical_fng.py backend/tests/test_historical_fng.py
git commit -m "feat: add Fear & Greed historical data ingestion"
```

---

## Task 5: DeFi Llama Historical Ingestion (TVL, DEX Volume, Stablecoin)

**Files:**
- Create: `backend/app/ingestion/historical_defillama.py`
- Test: `backend/tests/test_historical_defillama.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_historical_defillama.py
import pytest
import httpx
import respx
from datetime import date
from sqlalchemy import select, func
from app.database import init_db, get_session, HistoricalData
from app.ingestion.historical_defillama import (
    ingest_tvl_history,
    ingest_dex_volume_history,
    ingest_stablecoin_history,
)


@pytest.mark.asyncio
@respx.mock
async def test_ingest_tvl_history():
    mock_data = [
        {"date": 1711324800, "tvl": 4000000000},
        {"date": 1711411200, "tvl": 4100000000},
        {"date": 1711497600, "tvl": 4200000000},
    ]
    respx.get("https://api.llama.fi/v2/historicalChainTvl/Solana").mock(
        return_value=httpx.Response(200, json=mock_data)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count = await ingest_tvl_history(engine, client)
    assert count == 3

    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData).where(HistoricalData.source == "tvl").order_by(HistoricalData.date)
        )
        rows = result.scalars().all()
        assert len(rows) == 3
        assert rows[2].value == pytest.approx(4.2e9)
    await engine.dispose()


@pytest.mark.asyncio
@respx.mock
async def test_ingest_tvl_skips_if_exists():
    respx.get("https://api.llama.fi/v2/historicalChainTvl/Solana").mock(
        return_value=httpx.Response(200, json=[{"date": 1711324800, "tvl": 4e9}])
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count1 = await ingest_tvl_history(engine, client)
        count2 = await ingest_tvl_history(engine, client)
    assert count1 == 1
    assert count2 == 0
    await engine.dispose()


@pytest.mark.asyncio
@respx.mock
async def test_ingest_dex_volume_history():
    mock_data = {
        "totalDataChart": [
            [1711324800, 500000000],
            [1711411200, 600000000],
        ]
    }
    respx.get("https://api.llama.fi/overview/dexs/solana").mock(
        return_value=httpx.Response(200, json=mock_data)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count = await ingest_dex_volume_history(engine, client)
    assert count == 2

    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData).where(HistoricalData.source == "dex_volume").order_by(HistoricalData.date)
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        assert rows[1].value == pytest.approx(6e8)
    await engine.dispose()


@pytest.mark.asyncio
@respx.mock
async def test_ingest_stablecoin_history():
    # Stablecoin charts return an array of daily objects with totalCirculatingUSD
    mock_data = [
        {"date": "1711324800", "totalCirculatingUSD": {"peggedUSD": 3000000000}},
        {"date": "1711411200", "totalCirculatingUSD": {"peggedUSD": 3100000000}},
        {"date": "1711497600", "totalCirculatingUSD": {"peggedUSD": 3200000000}},
    ]
    respx.get("https://stablecoins.llama.fi/stablecoincharts/Solana").mock(
        return_value=httpx.Response(200, json=mock_data)
    )
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    async with httpx.AsyncClient() as client:
        count = await ingest_stablecoin_history(engine, client)
    assert count == 3

    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData).where(HistoricalData.source == "stablecoin_supply").order_by(HistoricalData.date)
        )
        rows = result.scalars().all()
        assert len(rows) == 3
        assert rows[2].value == pytest.approx(3.2e9)
    await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_historical_defillama.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/ingestion/historical_defillama.py
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, func

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)


async def _check_existing(engine, source: str) -> bool:
    async with get_session(engine) as session:
        result = await session.execute(
            select(func.count()).select_from(HistoricalData).where(HistoricalData.source == source)
        )
        return result.scalar() > 0


async def ingest_tvl_history(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch full Solana TVL history from DeFi Llama."""
    source = "tvl"
    if await _check_existing(engine, source):
        logger.info("TVL history already ingested, skipping")
        return 0

    resp = await http_client.get(
        "https://api.llama.fi/v2/historicalChainTvl/Solana", timeout=30.0
    )
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for entry in data:
        ts = int(entry.get("date", 0))
        tvl = float(entry.get("tvl", 0))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        rows.append(HistoricalData(source=source, date=dt, value=tvl, metadata_json=None))

    async with get_session(engine) as session:
        session.add_all(rows)
        await session.commit()

    logger.info(f"Ingested {len(rows)} TVL history rows")
    return len(rows)


async def ingest_dex_volume_history(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch Solana DEX volume history from DeFi Llama."""
    source = "dex_volume"
    if await _check_existing(engine, source):
        logger.info("DEX volume history already ingested, skipping")
        return 0

    resp = await http_client.get(
        "https://api.llama.fi/overview/dexs/solana", timeout=30.0
    )
    resp.raise_for_status()
    data = resp.json()
    chart = data.get("totalDataChart", [])

    rows = []
    for entry in chart:
        ts = int(entry[0])
        volume = float(entry[1])
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        rows.append(HistoricalData(source=source, date=dt, value=volume, metadata_json=None))

    async with get_session(engine) as session:
        session.add_all(rows)
        await session.commit()

    logger.info(f"Ingested {len(rows)} DEX volume history rows")
    return len(rows)


async def ingest_stablecoin_history(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch Solana stablecoin supply history from DeFi Llama."""
    source = "stablecoin_supply"
    if await _check_existing(engine, source):
        logger.info("Stablecoin history already ingested, skipping")
        return 0

    resp = await http_client.get(
        "https://stablecoins.llama.fi/stablecoincharts/Solana", timeout=30.0
    )
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for entry in data:
        ts = int(entry.get("date", 0))
        pegged = entry.get("totalCirculatingUSD", {})
        supply = float(pegged.get("peggedUSD", 0)) if isinstance(pegged, dict) else 0.0
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        rows.append(HistoricalData(source=source, date=dt, value=supply, metadata_json=None))

    async with get_session(engine) as session:
        session.add_all(rows)
        await session.commit()

    logger.info(f"Ingested {len(rows)} stablecoin supply history rows")
    return len(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_historical_defillama.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/historical_defillama.py backend/tests/test_historical_defillama.py
git commit -m "feat: add DeFi Llama historical data ingestion (TVL, DEX volume, stablecoin)"
```

---

## Task 6: Ingestion Runner (Orchestrator)

**Files:**
- Create: `backend/app/ingestion/runner.py`
- Test: `backend/tests/test_ingestion_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_ingestion_runner.py
import pytest
import httpx
import respx
import tempfile
import os
from sqlalchemy import select, func
from app.database import init_db, get_session, HistoricalData
from app.ingestion.runner import run_backfill


@pytest.mark.asyncio
@respx.mock
async def test_run_backfill_ingests_all_sources():
    # Mock external APIs
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(200, json={"data": [
            {"value": "50", "value_classification": "Neutral", "timestamp": "1711497600"},
        ]})
    )
    respx.get("https://api.llama.fi/v2/historicalChainTvl/Solana").mock(
        return_value=httpx.Response(200, json=[{"date": 1711497600, "tvl": 4e9}])
    )
    respx.get("https://api.llama.fi/overview/dexs/solana").mock(
        return_value=httpx.Response(200, json={"totalDataChart": [[1711497600, 5e8]]})
    )
    respx.get("https://stablecoins.llama.fi/stablecoincharts/Solana").mock(
        return_value=httpx.Response(200, json=[
            {"date": "1711497600", "totalCirculatingUSD": {"peggedUSD": 3e9}},
        ])
    )

    csv_content = "time,open,high,low,close,#1\n1711497600,185.2,192.1,183.0,190.5,\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name

    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        async with httpx.AsyncClient() as client:
            result = await run_backfill(engine, client, sol_csv_path=csv_path)

        assert result["sol_ohlcv"] == 1
        assert result["fear_greed"] == 1
        assert result["tvl"] == 1
        assert result["dex_volume"] == 1
        assert result["stablecoin_supply"] == 1
        await engine.dispose()
    finally:
        os.unlink(csv_path)


@pytest.mark.asyncio
@respx.mock
async def test_run_backfill_idempotent():
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(200, json={"data": [
            {"value": "50", "value_classification": "Neutral", "timestamp": "1711497600"},
        ]})
    )
    respx.get("https://api.llama.fi/v2/historicalChainTvl/Solana").mock(
        return_value=httpx.Response(200, json=[{"date": 1711497600, "tvl": 4e9}])
    )
    respx.get("https://api.llama.fi/overview/dexs/solana").mock(
        return_value=httpx.Response(200, json={"totalDataChart": [[1711497600, 5e8]]})
    )
    respx.get("https://stablecoins.llama.fi/stablecoincharts/Solana").mock(
        return_value=httpx.Response(200, json=[
            {"date": "1711497600", "totalCirculatingUSD": {"peggedUSD": 3e9}},
        ])
    )

    csv_content = "time,open,high,low,close,#1\n1711497600,185.2,192.1,183.0,190.5,\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name

    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        async with httpx.AsyncClient() as client:
            await run_backfill(engine, client, sol_csv_path=csv_path)
            result2 = await run_backfill(engine, client, sol_csv_path=csv_path)

        # All should be 0 on second run
        assert all(v == 0 for v in result2.values())
        await engine.dispose()
    finally:
        os.unlink(csv_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ingestion_runner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/ingestion/runner.py
import logging

import httpx

from app.ingestion.sol_csv import ingest_sol_csv
from app.ingestion.historical_fng import ingest_fear_greed_history
from app.ingestion.historical_defillama import (
    ingest_tvl_history,
    ingest_dex_volume_history,
    ingest_stablecoin_history,
)

logger = logging.getLogger(__name__)


async def run_backfill(
    engine,
    http_client: httpx.AsyncClient,
    sol_csv_path: str = "data/CRYPTO_SOLUSD, 1D_81fb0.csv",
) -> dict[str, int]:
    """Run all historical data ingestion. Idempotent — skips sources already ingested.

    Returns dict of source_name -> rows_inserted.
    """
    logger.info("Starting historical data backfill...")
    results = {}

    results["sol_ohlcv"] = await ingest_sol_csv(engine, sol_csv_path)
    results["fear_greed"] = await ingest_fear_greed_history(engine, http_client)
    results["tvl"] = await ingest_tvl_history(engine, http_client)
    results["dex_volume"] = await ingest_dex_volume_history(engine, http_client)
    results["stablecoin_supply"] = await ingest_stablecoin_history(engine, http_client)

    total = sum(results.values())
    if total > 0:
        logger.info(f"Backfill complete: {results}")
    else:
        logger.info("Backfill skipped — all sources already ingested")

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ingestion_runner.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/runner.py backend/tests/test_ingestion_runner.py
git commit -m "feat: add ingestion runner to orchestrate historical data backfill"
```

---

## Task 7: Correlation Engine

**Files:**
- Create: `backend/app/analysis/correlation.py`
- Test: `backend/tests/test_correlation.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_correlation.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_correlation.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/analysis/correlation.py
import logging
from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import select

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 365
CORRELATION_THRESHOLD = 0.15
FORWARD_RETURN_DAYS = 7
LAGS = [1, 3, 7, 14]

# Sources that map to scorable factors (source_name in historical_data)
FACTOR_SOURCES = ["tvl", "fear_greed", "dex_volume", "stablecoin_supply"]


@dataclass
class CorrelationResult:
    name: str
    label: str
    correlation: float  # Pearson r
    optimal_lag_days: int
    weight: float  # normalized |r|, sums to 1.0 across all in_score factors
    in_score: bool  # True if |r| >= CORRELATION_THRESHOLD and enough data


FACTOR_LABELS = {
    "tvl": "Total Value Locked",
    "fear_greed": "Fear & Greed Index",
    "dex_volume": "DEX Volume",
    "stablecoin_supply": "Stablecoin Supply (7d delta)",
}

# Factors that need 7-day delta transformation before correlation
DELTA_FACTORS = {"stablecoin_supply"}


async def _load_series(engine, source: str) -> dict[date, float]:
    """Load a factor's historical data as a date->value dict.

    For factors in DELTA_FACTORS, computes 7-day change (delta) instead of raw value.
    """
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData.date, HistoricalData.value)
            .where(HistoricalData.source == source)
            .order_by(HistoricalData.date)
        )
        raw = [(row.date, row.value) for row in result.all()]

    if source not in DELTA_FACTORS:
        return {d: v for d, v in raw}

    # Compute 7-day delta: value[i] - value[i-7]
    from datetime import timedelta
    raw_dict = {d: v for d, v in raw}
    delta_series = {}
    for d, v in raw:
        past_date = d - timedelta(days=7)
        if past_date in raw_dict:
            delta_series[d] = v - raw_dict[past_date]
    return delta_series


def _compute_forward_returns(prices: dict[date, float], days: int = 7) -> dict[date, float]:
    """Compute forward returns (pct change) for each date."""
    sorted_dates = sorted(prices.keys())
    returns = {}
    for i, d in enumerate(sorted_dates):
        # Find the price `days` forward
        target_idx = i + days
        if target_idx < len(sorted_dates):
            future_price = prices[sorted_dates[target_idx]]
            current_price = prices[d]
            if current_price > 0:
                returns[d] = (future_price - current_price) / current_price
    return returns


def _pearson_at_lag(
    factor_values: dict[date, float],
    forward_returns: dict[date, float],
    lag: int,
) -> float | None:
    """Compute Pearson r between factor (lagged) and forward returns."""
    from datetime import timedelta

    pairs_x = []
    pairs_y = []
    for d, ret in forward_returns.items():
        lagged_date = d - timedelta(days=lag)
        if lagged_date in factor_values:
            pairs_x.append(factor_values[lagged_date])
            pairs_y.append(ret)

    if len(pairs_x) < 30:  # need minimum overlap
        return None

    x = np.array(pairs_x)
    y = np.array(pairs_y)

    # Handle constant arrays
    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0

    r = np.corrcoef(x, y)[0, 1]
    return float(r) if np.isfinite(r) else None


async def compute_correlations(engine) -> list[CorrelationResult]:
    """Compute rolling Pearson correlation for each factor against SOL forward returns.

    Returns a list of CorrelationResult with weights normalized so in_score factors sum to 1.0.
    """
    # Load SOL price data
    sol_prices = await _load_series(engine, "sol_ohlcv")
    if len(sol_prices) < MIN_DATA_POINTS:
        logger.warning(f"Only {len(sol_prices)} SOL price points, need {MIN_DATA_POINTS}")
        return []

    forward_returns = _compute_forward_returns(sol_prices, FORWARD_RETURN_DAYS)

    results = []
    for source in FACTOR_SOURCES:
        factor_data = await _load_series(engine, source)
        if len(factor_data) < MIN_DATA_POINTS:
            logger.info(f"Skipping {source}: only {len(factor_data)} data points (need {MIN_DATA_POINTS})")
            continue

        # Test each lag, pick strongest |r|
        best_r = None
        best_lag = LAGS[0]
        for lag in LAGS:
            r = _pearson_at_lag(factor_data, forward_returns, lag)
            if r is not None and (best_r is None or abs(r) > abs(best_r)):
                best_r = r
                best_lag = lag

        if best_r is None:
            continue

        results.append(CorrelationResult(
            name=source,
            label=FACTOR_LABELS.get(source, source),
            correlation=round(best_r, 4),
            optimal_lag_days=best_lag,
            weight=0.0,  # placeholder, normalized below
            in_score=abs(best_r) >= CORRELATION_THRESHOLD,
        ))

    # Normalize weights for in_score factors
    scored = [r for r in results if r.in_score]
    if scored:
        total_abs_r = sum(abs(r.correlation) for r in scored)
        for r in scored:
            r.weight = round(abs(r.correlation) / total_abs_r, 4)

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_correlation.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/correlation.py backend/tests/test_correlation.py
git commit -m "feat: add correlation engine with multi-lag Pearson analysis and weight derivation"
```

---

## Task 8: Score Backfill Engine

**Files:**
- Create: `backend/app/analysis/score_backfill.py`
- Test: `backend/tests/test_score_backfill.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_score_backfill.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_score_backfill.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/analysis/score_backfill.py
import json
import logging
import math
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select, func

from app.database import get_session, HistoricalData, DailyScore
from app.analysis.correlation import CorrelationResult, _load_series

logger = logging.getLogger(__name__)

ROLLING_WINDOW = 90


async def backfill_scores(engine, correlations: list[CorrelationResult]) -> int:
    """Compute historical daily scores and store in daily_scores table.

    Uses 90-day rolling mean/std for z-score computation.
    Returns number of rows inserted (0 if already backfilled).
    """
    # Check if already backfilled
    async with get_session(engine) as session:
        result = await session.execute(select(func.count()).select_from(DailyScore))
        if result.scalar() > 0:
            logger.info("Daily scores already backfilled, skipping")
            return 0

    scored_factors = [c for c in correlations if c.in_score]
    if not scored_factors:
        logger.warning("No scored factors available for backfill")
        return 0

    # Load all factor data using _load_series (handles delta transforms for stablecoin_supply)
    factor_series: dict[str, dict[date, float]] = {}
    for factor in scored_factors:
        factor_series[factor.name] = await _load_series(engine, factor.name)

    # Load SOL price dates to know which days to score
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData.date)
            .where(HistoricalData.source == "sol_ohlcv")
            .order_by(HistoricalData.date)
        )
        all_dates = [row.date for row in result.all()]

    # Need at least ROLLING_WINDOW days before we can compute z-scores
    if len(all_dates) < ROLLING_WINDOW:
        logger.warning(f"Only {len(all_dates)} dates, need at least {ROLLING_WINDOW}")
        return 0

    scores_to_insert = []
    for idx in range(ROLLING_WINDOW, len(all_dates)):
        current_date = all_dates[idx]
        window_start_idx = idx - ROLLING_WINDOW
        window_dates = all_dates[window_start_idx:idx]

        factors_json = {}
        weighted_z_sum = 0.0
        total_weight = 0.0
        factors_available = 0

        for factor in scored_factors:
            series = factor_series.get(factor.name, {})
            current_val = series.get(current_date)
            if current_val is None:
                continue

            # Compute rolling stats over window
            window_vals = [series.get(d) for d in window_dates if d in series]
            if len(window_vals) < 30:  # need minimum window data
                continue

            arr = np.array(window_vals)
            mean = float(np.mean(arr))
            std = float(np.std(arr))
            if std == 0:
                z_score = 0.0
            else:
                z_score = (current_val - mean) / std

            # sign(r) * |weight| * z_score
            signed_contribution = math.copysign(1, factor.correlation) * factor.weight * z_score
            weighted_z_sum += signed_contribution
            total_weight += factor.weight
            factors_available += 1

            factors_json[factor.name] = {
                "value": current_val,
                "z_score": round(z_score, 4),
                "weight": factor.weight,
                "contribution": round(signed_contribution, 4),
            }

        if factors_available == 0:
            continue

        # Pass weighted z-sum directly into tanh (weights already sum to 1.0)
        score = 50 + 50 * math.tanh(weighted_z_sum / 2)
        score = max(0, min(100, score))

        scores_to_insert.append(DailyScore(
            date=current_date,
            score=round(score, 1),
            factors_json=json.dumps(factors_json),
            factors_available=factors_available,
            factors_total=len(scored_factors),
        ))

    # Batch insert
    async with get_session(engine) as session:
        session.add_all(scores_to_insert)
        await session.commit()

    logger.info(f"Backfilled {len(scores_to_insert)} daily scores")
    return len(scores_to_insert)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_score_backfill.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/score_backfill.py backend/tests/test_score_backfill.py
git commit -m "feat: add score backfill engine with 90-day rolling z-scores"
```

---

## Task 9: API Endpoint — `/api/pulse/chart`

**Files:**
- Create: `backend/app/routers/pulse_chart.py`
- Test: `backend/tests/test_pulse_chart.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pulse_chart.py
import pytest
import json
from datetime import date, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import init_db, get_session, HistoricalData, DailyScore
from app.routers.pulse_chart import router, set_engine


def _make_app(engine):
    app = FastAPI()
    app.include_router(router)
    set_engine(engine)
    return app


@pytest.mark.asyncio
async def test_chart_endpoint_returns_candles_and_scores():
    engine = await init_db("sqlite+aiosqlite:///:memory:")

    async with get_session(engine) as session:
        base = date(2026, 2, 1)
        for i in range(60):
            d = base + timedelta(days=i)
            session.add(HistoricalData(
                source="sol_ohlcv", date=d, value=180 + i,
                metadata_json=json.dumps({"open": 179+i, "high": 185+i, "low": 175+i, "close": 180+i}),
            ))
            session.add(DailyScore(
                date=d, score=50 + i * 0.5,
                factors_json="{}", factors_available=3, factors_total=4,
            ))
        await session.commit()

    client = TestClient(_make_app(engine))
    resp = client.get("/api/pulse/chart?range=30d")
    assert resp.status_code == 200
    data = resp.json()
    assert "candles" in data
    assert "scores" in data
    assert data["range"] == "30d"
    assert len(data["candles"]) == 30
    assert len(data["scores"]) == 30
    # Check candle structure
    candle = data["candles"][0]
    assert "time" in candle
    assert "open" in candle
    assert "high" in candle
    assert "low" in candle
    assert "close" in candle
    # Check score structure
    score = data["scores"][0]
    assert "time" in score
    assert "score" in score
    await engine.dispose()


@pytest.mark.asyncio
async def test_chart_endpoint_range_all():
    engine = await init_db("sqlite+aiosqlite:///:memory:")

    async with get_session(engine) as session:
        base = date(2022, 1, 1)
        for i in range(100):
            d = base + timedelta(days=i)
            session.add(HistoricalData(
                source="sol_ohlcv", date=d, value=100 + i,
                metadata_json=json.dumps({"open": 99+i, "high": 105+i, "low": 95+i, "close": 100+i}),
            ))
            session.add(DailyScore(
                date=d, score=50.0,
                factors_json="{}", factors_available=2, factors_total=4,
            ))
        await session.commit()

    client = TestClient(_make_app(engine))
    resp = client.get("/api/pulse/chart?range=all")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candles"]) == 100
    assert data["range"] == "all"
    await engine.dispose()


@pytest.mark.asyncio
async def test_chart_endpoint_invalid_range():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    client = TestClient(_make_app(engine))
    resp = client.get("/api/pulse/chart?range=5d")
    assert resp.status_code == 400
    await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pulse_chart.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/routers/pulse_chart.py
import calendar
import json
from datetime import date, timedelta, time as dt_time, datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.database import get_session, HistoricalData, DailyScore

router = APIRouter(prefix="/api/pulse", tags=["pulse-chart"])

_engine = None

RANGE_DAYS = {
    "30d": 30,
    "90d": 90,
    "1y": 365,
    "all": None,
}


def set_engine(engine):
    global _engine
    _engine = engine


@router.get("/chart")
async def get_chart(range: str = Query("30d")):
    if range not in RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Invalid range: {range}. Valid: {', '.join(RANGE_DAYS)}")

    days = RANGE_DAYS[range]
    cutoff = date.today() - timedelta(days=days) if days else None

    async with get_session(_engine) as session:
        # Fetch candles
        candle_query = (
            select(HistoricalData)
            .where(HistoricalData.source == "sol_ohlcv")
            .order_by(HistoricalData.date)
        )
        if cutoff:
            candle_query = candle_query.where(HistoricalData.date >= cutoff)

        result = await session.execute(candle_query)
        candle_rows = result.scalars().all()

        candles = []
        for row in candle_rows:
            meta = json.loads(row.metadata_json) if row.metadata_json else {}
            candles.append({
                "time": int(calendar.timegm(row.date.timetuple())),
                "open": meta.get("open", row.value),
                "high": meta.get("high", row.value),
                "low": meta.get("low", row.value),
                "close": meta.get("close", row.value),
            })

        # Fetch scores
        score_query = select(DailyScore).order_by(DailyScore.date)
        if cutoff:
            score_query = score_query.where(DailyScore.date >= cutoff)

        result = await session.execute(score_query)
        score_rows = result.scalars().all()

        scores = [
            {"time": int(calendar.timegm(row.date.timetuple())), "score": row.score}
            for row in score_rows
        ]

    return {"candles": candles, "scores": scores, "range": range}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_pulse_chart.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/pulse_chart.py backend/tests/test_pulse_chart.py
git commit -m "feat: add /api/pulse/chart endpoint with range filtering"
```

---

## Task 10: API Endpoint — `/api/pulse/correlations`

**Files:**
- Create: `backend/app/routers/pulse_correlations.py`
- Test: `backend/tests/test_pulse_correlations.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pulse_correlations.py
import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.analysis.correlation import CorrelationResult
from app.routers.pulse_correlations import router, set_correlations


def _make_app():
    app = FastAPI()
    app.include_router(router)
    return app


def test_correlations_endpoint_returns_factors():
    mock_correlations = [
        CorrelationResult(name="tvl", label="Total Value Locked", correlation=0.42, optimal_lag_days=3, weight=0.55, in_score=True),
        CorrelationResult(name="fear_greed", label="Fear & Greed Index", correlation=0.34, optimal_lag_days=7, weight=0.45, in_score=True),
    ]
    set_correlations(mock_correlations, datetime(2026, 3, 27, tzinfo=timezone.utc))

    client = TestClient(_make_app())
    resp = client.get("/api/pulse/correlations")
    assert resp.status_code == 200
    data = resp.json()

    assert "factors" in data
    assert len(data["factors"]) == 2
    assert data["factors"][0]["name"] == "tvl"
    assert data["factors"][0]["correlation"] == 0.42
    assert data["factors"][0]["weight"] == 0.55
    assert data["factors"][0]["in_score"] is True
    assert "last_computed" in data


def test_correlations_endpoint_empty():
    set_correlations([], datetime(2026, 3, 27, tzinfo=timezone.utc))

    client = TestClient(_make_app())
    resp = client.get("/api/pulse/correlations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["factors"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pulse_correlations.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/routers/pulse_correlations.py
from datetime import datetime, timezone

from fastapi import APIRouter

from app.analysis.correlation import CorrelationResult

router = APIRouter(prefix="/api/pulse", tags=["pulse-correlations"])

_correlations: list[CorrelationResult] = []
_last_computed: datetime | None = None


def set_correlations(correlations: list[CorrelationResult], computed_at: datetime | None = None):
    global _correlations, _last_computed
    _correlations = correlations
    _last_computed = computed_at or datetime.now(timezone.utc)


@router.get("/correlations")
async def get_correlations():
    factors = [
        {
            "name": r.name,
            "label": r.label,
            "correlation": r.correlation,
            "optimal_lag_days": r.optimal_lag_days,
            "weight": r.weight,
            "in_score": r.in_score,
        }
        for r in _correlations
    ]
    return {
        "factors": factors,
        "last_computed": _last_computed.isoformat() if _last_computed else None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_pulse_correlations.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/pulse_correlations.py backend/tests/test_pulse_correlations.py
git commit -m "feat: add /api/pulse/correlations endpoint"
```

---

## Task 11: API Endpoint — `/api/pulse/ecosystem`

**Files:**
- Create: `backend/app/routers/pulse_ecosystem.py`
- Test: `backend/tests/test_pulse_ecosystem.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pulse_ecosystem.py
import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.cache import MemoryCache
from app.database import init_db
from app.routers.pulse_ecosystem import router, set_cache, set_engine


def _make_app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_ecosystem_returns_live_metrics():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    cache = MemoryCache()
    cache.set("solana_rpc:tps", {"value": 3200, "fetched_at": "2026-03-27T12:00:00Z"}, ttl=600)
    cache.set("solana_rpc:priority_fees", {"value": 5000, "fetched_at": "2026-03-27T12:00:00Z"}, ttl=600)
    cache.set("solana_rpc:stablecoin_supply", {
        "value": 25e9, "metadata": {"usdc": 15e9, "usdt": 10e9},
        "fetched_at": "2026-03-27T12:00:00Z",
    }, ttl=600)
    cache.set("google_trends:google_trends", {
        "value": 0, "metadata": {"solana": 75, "ethereum": 60, "bitcoin": 80},
        "fetched_at": "2026-03-27T12:00:00Z",
    }, ttl=600)
    set_cache(cache)
    set_engine(engine)

    client = TestClient(_make_app())
    resp = client.get("/api/pulse/ecosystem")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "last_updated" in data

    names = [m["name"] for m in data["metrics"]]
    assert "tps" in names
    assert "priority_fees" in names
    # Verify sparkline field exists
    tps_metric = next(m for m in data["metrics"] if m["name"] == "tps")
    assert "sparkline" in tps_metric
    assert isinstance(tps_metric["sparkline"], list)
    await engine.dispose()


@pytest.mark.asyncio
async def test_ecosystem_empty_cache():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    cache = MemoryCache()
    set_cache(cache)
    set_engine(engine)

    client = TestClient(_make_app())
    resp = client.get("/api/pulse/ecosystem")
    assert resp.status_code == 200
    data = resp.json()
    assert data["metrics"] == []
    await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pulse_ecosystem.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/routers/pulse_ecosystem.py
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter
from sqlalchemy import select

from app.cache import MemoryCache
from app.database import get_session, MetricData

router = APIRouter(prefix="/api/pulse", tags=["pulse-ecosystem"])

_cache: MemoryCache | None = None
_engine = None


def set_cache(cache: MemoryCache):
    global _cache
    _cache = cache


def set_engine(engine):
    global _engine
    _engine = engine


def _get_cached(source: str, metric: str) -> dict | None:
    if _cache is None:
        return None
    return _cache.get(f"{source}:{metric}")


async def _get_sparkline(source: str, metric_name: str, days: int = 7) -> list[float]:
    """Get last N days of metric values from DB for sparkline."""
    if _engine is None:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_session(_engine) as session:
        result = await session.execute(
            select(MetricData.value)
            .where(
                MetricData.source == source,
                MetricData.metric_name == metric_name,
                MetricData.fetched_at >= cutoff,
            )
            .order_by(MetricData.fetched_at)
        )
        return [row.value for row in result.all()]


def _direction(sparkline: list[float]) -> str | None:
    if len(sparkline) < 2:
        return None
    return "up" if sparkline[-1] >= sparkline[0] else "down"


@router.get("/ecosystem")
async def get_ecosystem():
    metrics = []

    tps = _get_cached("solana_rpc", "tps")
    if tps:
        sparkline = await _get_sparkline("solana_rpc", "tps")
        metrics.append({
            "name": "tps",
            "label": "Network TPS",
            "current": tps["value"],
            "sparkline": sparkline,
            "direction": _direction(sparkline),
        })

    fees = _get_cached("solana_rpc", "priority_fees")
    if fees:
        sparkline = await _get_sparkline("solana_rpc", "priority_fees")
        metrics.append({
            "name": "priority_fees",
            "label": "Priority Fees",
            "current": fees["value"],
            "sparkline": sparkline,
            "direction": _direction(sparkline),
        })

    stablecoin = _get_cached("solana_rpc", "stablecoin_supply")
    if stablecoin:
        md = stablecoin.get("metadata", {})
        sparkline = await _get_sparkline("solana_rpc", "stablecoin_supply")
        metrics.append({
            "name": "stablecoin_supply",
            "label": "Stablecoin Supply",
            "current": stablecoin["value"],
            "sparkline": sparkline,
            "direction": _direction(sparkline),
            "sub_values": {"usdc": md.get("usdc", 0), "usdt": md.get("usdt", 0)},
        })

    trends = _get_cached("google_trends", "google_trends")
    if trends:
        md = trends.get("metadata", {})
        metrics.append({
            "name": "google_trends",
            "label": "Google Trends",
            "current": md.get("solana", 0),
            "sparkline": [],
            "direction": None,
            "sub_values": {"ethereum": md.get("ethereum", 0), "bitcoin": md.get("bitcoin", 0)},
        })

    return {
        "metrics": metrics,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_pulse_ecosystem.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/pulse_ecosystem.py backend/tests/test_pulse_ecosystem.py
git commit -m "feat: add /api/pulse/ecosystem endpoint for live supplementary metrics"
```

---

## Task 12: Wire Up Backend — main.py Integration

**Files:**
- Modify: `backend/app/main.py:1-84`
- Modify: `backend/app/routers/pulse.py` (remove old endpoint)

- [ ] **Step 1: Update main.py**

Replace `backend/app/main.py` with:

```python
# backend/app/main.py
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache import MemoryCache
from app.config import get_settings
from app.database import init_db
from app.scheduler import scheduler, register_fetcher_job
from app.fetchers.dexscreener import DexScreenerFetcher
from app.fetchers.solana_rpc import SolanaRpcFetcher
from app.fetchers.coingecko import CoinGeckoFetcher
from app.fetchers.defillama import DefiLlamaFetcher
from app.fetchers.fear_greed import FearGreedFetcher
from app.fetchers.google_trends import GoogleTrendsFetcher
from app.routers.health import router as health_router, set_fetchers
from app.routers.pulse_chart import router as chart_router, set_engine as set_chart_engine
from app.routers.pulse_correlations import router as correlations_router, set_correlations
from app.routers.pulse_ecosystem import router as ecosystem_router, set_cache as set_ecosystem_cache, set_engine as set_ecosystem_engine
from app.ingestion.runner import run_backfill
from app.analysis.correlation import compute_correlations
from app.analysis.score_backfill import backfill_scores

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

cache = MemoryCache()
http_client: httpx.AsyncClient | None = None
db_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, db_engine

    # Startup
    settings = get_settings()
    db_engine = await init_db(settings.database_url)
    http_client = httpx.AsyncClient()

    # Run historical data backfill (idempotent)
    await run_backfill(db_engine, http_client)

    # Compute correlations and backfill scores
    correlations = await compute_correlations(db_engine)
    set_correlations(correlations)
    await backfill_scores(db_engine, correlations)

    # Set engine for chart endpoint
    set_chart_engine(db_engine)

    # Create fetchers
    dexscreener = DexScreenerFetcher(cache=cache, http_client=http_client, db_engine=db_engine)
    solana_rpc = SolanaRpcFetcher(cache=cache, http_client=http_client, rpc_url=settings.solana_rpc_url, db_engine=db_engine)
    coingecko = CoinGeckoFetcher(cache=cache, http_client=http_client, api_key=settings.coingecko_api_key, db_engine=db_engine)
    defillama = DefiLlamaFetcher(cache=cache, http_client=http_client, db_engine=db_engine)
    fear_greed = FearGreedFetcher(cache=cache, http_client=http_client, db_engine=db_engine)
    google_trends = GoogleTrendsFetcher(cache=cache, http_client=http_client, db_engine=db_engine)

    all_fetchers = [dexscreener, solana_rpc, coingecko, defillama, fear_greed, google_trends]
    set_fetchers(all_fetchers)
    set_ecosystem_cache(cache)
    set_ecosystem_engine(db_engine)

    # Register scheduled jobs
    register_fetcher_job(dexscreener, settings.fetch_interval_dexscreener)
    register_fetcher_job(solana_rpc, settings.fetch_interval_rpc)
    register_fetcher_job(coingecko, settings.fetch_interval_coingecko)
    register_fetcher_job(defillama, settings.fetch_interval_defillama)
    register_fetcher_job(fear_greed, settings.fetch_interval_fear_greed)
    register_fetcher_job(google_trends, settings.fetch_interval_google_trends)

    # Run initial fetch
    for f in all_fetchers:
        await f.run()

    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown(wait=True)
    await http_client.aclose()
    await db_engine.dispose()


app = FastAPI(title="Candle Launch Terminal", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chart_router)
app.include_router(correlations_router)
app.include_router(ecosystem_router)
```

- [ ] **Step 2: Remove old pulse router**

Delete the `@router.get("")` endpoint from `backend/app/routers/pulse.py`. The file can be deleted entirely since the three new routers replace it.

```bash
rm backend/app/routers/pulse.py
```

- [ ] **Step 3: Remove old pulse router test**

The old `test_pulse_router.py` tests the removed endpoint. Delete it:

```bash
rm backend/tests/test_pulse_router.py
```

- [ ] **Step 4: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/
git rm backend/app/routers/pulse.py backend/tests/test_pulse_router.py
git commit -m "feat: wire up new pulse endpoints, ingestion, and correlation in main.py"
```

---

## Task 13: Frontend — TypeScript Types and API Client

**Files:**
- Create: `frontend/src/types/pulse.ts`
- Create: `frontend/src/api/pulse.ts`

- [ ] **Step 1: Create TypeScript interfaces**

```typescript
// frontend/src/types/pulse.ts

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface ScorePoint {
  time: number;
  score: number;
}

export interface ChartData {
  candles: Candle[];
  scores: ScorePoint[];
  range: string;
}

export interface CorrelationFactor {
  name: string;
  label: string;
  correlation: number;
  optimal_lag_days: number;
  weight: number;
  in_score: boolean;
}

export interface CorrelationsData {
  factors: CorrelationFactor[];
  last_computed: string | null;
}

export interface EcosystemMetric {
  name: string;
  label: string;
  current: number;
  sparkline: number[];
  direction: "up" | "down" | null;
  sub_values?: Record<string, number>;
}

export interface EcosystemData {
  metrics: EcosystemMetric[];
  last_updated: string;
}

export type ChartRange = "30d" | "90d" | "1y" | "all";
```

- [ ] **Step 2: Create API client functions**

```typescript
// frontend/src/api/pulse.ts
import { apiFetch } from "./client";
import type { ChartData, CorrelationsData, EcosystemData, ChartRange } from "../types/pulse";

export function fetchChart(range: ChartRange = "30d"): Promise<ChartData> {
  return apiFetch<ChartData>(`/pulse/chart?range=${range}`);
}

export function fetchCorrelations(): Promise<CorrelationsData> {
  return apiFetch<CorrelationsData>("/pulse/correlations");
}

export function fetchEcosystem(): Promise<EcosystemData> {
  return apiFetch<EcosystemData>("/pulse/ecosystem");
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/pulse.ts frontend/src/api/pulse.ts
git commit -m "feat: add TypeScript types and API client for new pulse endpoints"
```

---

## Task 14: Frontend — Install lightweight-charts, Remove recharts

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Remove recharts, add lightweight-charts**

Run:
```bash
cd frontend && npm uninstall recharts && npm install lightweight-charts
```

- [ ] **Step 2: Verify package.json updated**

Run: `cat frontend/package.json`
Expected: `recharts` removed from dependencies, `lightweight-charts` added.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: replace recharts with lightweight-charts"
```

---

## Task 15: Frontend — CandlestickChart Component

**Files:**
- Create: `frontend/src/components/charts/CandlestickChart.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/charts/CandlestickChart.tsx
import { useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import { createChart, type IChartApi, type ISeriesApi, ColorType } from "lightweight-charts";
import type { Candle, ScorePoint } from "../../types/pulse";

export interface CandlestickChartHandle {
  getChart: () => IChartApi | null;
}

interface CandlestickChartProps {
  candles: Candle[];
  scores: ScorePoint[];
  height?: number;
  syncedChart?: IChartApi | null;
}

function scoreToColors(score: number): { line: string; top: string; bottom: string } {
  if (score >= 70) {
    return {
      line: "rgba(0, 230, 118, 0)",
      top: "rgba(0, 230, 118, 0.15)",
      bottom: "rgba(0, 230, 118, 0.02)",
    };
  }
  if (score <= 30) {
    return {
      line: "rgba(255, 23, 68, 0)",
      top: "rgba(255, 23, 68, 0.15)",
      bottom: "rgba(255, 23, 68, 0.02)",
    };
  }
  const t = (score - 30) / 40;
  const r = Math.round(255 * (1 - t));
  const g = Math.round(230 * t);
  return {
    line: `rgba(${r}, ${g}, 68, 0)`,
    top: `rgba(${r}, ${g}, 68, 0.10)`,
    bottom: `rgba(${r}, ${g}, 68, 0.02)`,
  };
}

const CandlestickChart = forwardRef<CandlestickChartHandle, CandlestickChartProps>(
  function CandlestickChart({ candles, scores, height = 400, syncedChart }, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useImperativeHandle(ref, () => ({
    getChart: () => chartRef.current,
  }));

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#12121a" },
        textColor: "#6b7280",
        fontFamily: "'JetBrains Mono', monospace",
      },
      grid: {
        vertLines: { color: "#1e1e2e" },
        horzLines: { color: "#1e1e2e" },
      },
      width: containerRef.current.clientWidth,
      height,
      crosshair: { mode: 0 },
      timeScale: {
        borderColor: "#1e1e2e",
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: "#1e1e2e",
      },
    });

    // Background area series (rendered behind candles) for score-based gradient.
    // Uses the price scale but is invisible — fills the chart area with color.
    const bgSeries = chart.addAreaSeries({
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lineColor: "rgba(0,0,0,0)",
      topColor: "rgba(0,0,0,0)",
      bottomColor: "rgba(0,0,0,0)",
      priceScaleId: "",  // overlay, no own price scale
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#00e676",
      downColor: "#ff1744",
      borderUpColor: "#00e676",
      borderDownColor: "#ff1744",
      wickUpColor: "#00e676",
      wickDownColor: "#ff1744",
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    // Sync crosshair with the other chart
    if (syncedChart) {
      chart.subscribeCrosshairMove((param) => {
        if (param.time) {
          syncedChart.setCrosshairPosition(0, param.time, syncedChart.timeScale());
        } else {
          syncedChart.clearCrosshairPosition();
        }
      });
    }

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, [height, syncedChart]);

  // Update data
  useEffect(() => {
    if (!candleSeriesRef.current || !chartRef.current || candles.length === 0) return;

    candleSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.time as any,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // Score-based background: use area series at max price to fill chart bg
    if (scores.length > 0) {
      const scoreMap = new Map(scores.map((s) => [s.time, s.score]));
      const maxHigh = Math.max(...candles.map((c) => c.high));

      // Compute average score for overall background tint
      const avgScore = scores.reduce((sum, s) => sum + s.score, 0) / scores.length;
      const colors = scoreToColors(avgScore);

      // Get background area series (first series added)
      const allSeries = (chartRef.current as any)._private__seriesMap;
      // Simpler: just update options on a stored ref
      // For the initial implementation, set a single gradient based on average score
      const bgData = candles.map((c) => ({
        time: c.time as any,
        value: maxHigh * 1.05,
      }));

      // We'll find the bg series via the chart API
      // Since we can't easily access the bg series after creation,
      // we'll use the chart's background color change approach instead:
      // Apply per-candle coloring through the container's CSS gradient
      const container = containerRef.current;
      if (container) {
        container.style.background = `linear-gradient(to bottom, ${colors.top}, ${colors.bottom})`;
      }
    }
  }, [candles, scores]);

  return (
    <div className="bg-terminal-card border border-terminal-border p-2">
      <div ref={containerRef} style={{ borderRadius: "4px", overflow: "hidden" }} />
    </div>
  );
});

export default CandlestickChart;
```

> **Note:** The background gradient uses a CSS linear-gradient on the chart container based on the average health score, creating a translucent green/red tint behind the candles. This is simpler and more reliable than manipulating lightweight-charts' area series for background fills. The gradient updates when score data changes.
>
> **Crosshair sync:** Both `CandlestickChart` and `ScoreLine` use `forwardRef` and expose their chart instance via `getChart()`. The `Pulse` page wires bidirectional sync: candle chart gets `syncedChart={scoreChart}` and score line gets `syncedChart={candleChart}`. Each subscribes to crosshair moves and calls `setCrosshairPosition()` on the other.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/charts/CandlestickChart.tsx
git commit -m "feat: add CandlestickChart component with lightweight-charts"
```

---

## Task 16: Frontend — ScoreLine Component

**Files:**
- Create: `frontend/src/components/charts/ScoreLine.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/charts/ScoreLine.tsx
import { useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import { createChart, type IChartApi, ColorType } from "lightweight-charts";
import type { ScorePoint } from "../../types/pulse";

interface ScoreLineProps {
  scores: ScorePoint[];
  height?: number;
  syncedChart?: IChartApi | null;
}

export interface ScoreLineHandle {
  getChart: () => IChartApi | null;
}

const ScoreLine = forwardRef<ScoreLineHandle, ScoreLineProps>(
  function ScoreLine({ scores, height = 150, syncedChart }, ref) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);

    useImperativeHandle(ref, () => ({
      getChart: () => chartRef.current,
    }));

    useEffect(() => {
      if (!containerRef.current) return;

      const chart = createChart(containerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: "#12121a" },
          textColor: "#6b7280",
          fontFamily: "'JetBrains Mono', monospace",
        },
        grid: {
          vertLines: { color: "#1e1e2e" },
          horzLines: { color: "#1e1e2e" },
        },
        width: containerRef.current.clientWidth,
        height,
        crosshair: { mode: 0 },
        timeScale: {
          borderColor: "#1e1e2e",
          timeVisible: false,
        },
        rightPriceScale: {
          borderColor: "#1e1e2e",
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
      });

      const lineSeries = chart.addAreaSeries({
        lineColor: "#f0b90b",
        topColor: "rgba(240, 185, 11, 0.2)",
        bottomColor: "rgba(240, 185, 11, 0.0)",
        lineWidth: 2,
        priceFormat: { type: "custom", formatter: (price: number) => price.toFixed(0) },
      });

      chartRef.current = chart;

      // Sync crosshair with main chart
      if (syncedChart) {
        chart.subscribeCrosshairMove((param) => {
          if (param.time) {
            syncedChart.setCrosshairPosition(0, param.time, syncedChart.timeScale());
          } else {
            syncedChart.clearCrosshairPosition();
          }
        });
      }

      if (scores.length > 0) {
        lineSeries.setData(
          scores.map((s) => ({ time: s.time as any, value: s.score }))
        );
      }

      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          chart.applyOptions({ width: entry.contentRect.width });
        }
      });
      resizeObserver.observe(containerRef.current);

      return () => {
        resizeObserver.disconnect();
        chart.remove();
        chartRef.current = null;
      };
    }, [height, scores, syncedChart]);

    return (
      <div className="bg-terminal-card border border-terminal-border border-t-0 p-2">
        <div className="text-xs text-terminal-muted mb-1 px-2">Health Score (0–100)</div>
        <div ref={containerRef} />
      </div>
    );
  }
);

export default ScoreLine;
```

> **Crosshair sync:** Both `CandlestickChart` and `ScoreLine` accept a `syncedChart` prop pointing to the other chart instance. When one chart's crosshair moves, it calls `setCrosshairPosition()` on the other chart. The Pulse page wires this up using refs (see Task 20).

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/charts/ScoreLine.tsx
git commit -m "feat: add ScoreLine component for health score panel"
```

---

## Task 17: Frontend — RangeSelector Component

**Files:**
- Create: `frontend/src/components/charts/RangeSelector.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/charts/RangeSelector.tsx
import type { ChartRange } from "../../types/pulse";

interface RangeSelectorProps {
  selected: ChartRange;
  onChange: (range: ChartRange) => void;
}

const RANGES: { value: ChartRange; label: string }[] = [
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "1y", label: "1Y" },
  { value: "all", label: "All" },
];

export default function RangeSelector({ selected, onChange }: RangeSelectorProps) {
  return (
    <div className="flex gap-1">
      {RANGES.map((r) => (
        <button
          key={r.value}
          onClick={() => onChange(r.value)}
          className={`px-3 py-1 text-xs font-mono border transition-colors ${
            selected === r.value
              ? "bg-terminal-accent text-black border-terminal-accent"
              : "bg-terminal-card text-terminal-muted border-terminal-border hover:border-terminal-accent"
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/charts/RangeSelector.tsx
git commit -m "feat: add RangeSelector component for chart time range"
```

---

## Task 18: Frontend — EcosystemCard Component

**Files:**
- Create: `frontend/src/components/charts/EcosystemCard.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/charts/EcosystemCard.tsx
import type { EcosystemMetric } from "../../types/pulse";

interface EcosystemCardProps {
  metric: EcosystemMetric;
}

const MONETARY_METRICS = new Set(["stablecoin_supply"]);

function formatValue(value: number, name: string): string {
  if (MONETARY_METRICS.has(name)) {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    return `$${value.toLocaleString()}`;
  }
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toLocaleString();
}

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 60;
  const h = 20;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={w} height={h} className="inline-block">
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} />
    </svg>
  );
}

export default function EcosystemCard({ metric }: EcosystemCardProps) {
  const sparkColor = metric.direction === "up" ? "#00e676" : metric.direction === "down" ? "#ff1744" : "#6b7280";

  return (
    <div className="bg-terminal-card border border-terminal-border p-4">
      <div className="text-xs text-terminal-muted uppercase tracking-wider">{metric.label}</div>
      <div className="mt-1 flex items-center justify-between">
        <span className="text-xl font-bold text-terminal-text">
          {formatValue(metric.current, metric.name)}
        </span>
        {metric.sparkline.length > 1 && (
          <MiniSparkline data={metric.sparkline} color={sparkColor} />
        )}
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs">
        {metric.direction && (
          <span className={metric.direction === "up" ? "text-terminal-green" : "text-terminal-red"}>
            {metric.direction === "up" ? "▲" : "▼"}
          </span>
        )}
        {metric.sub_values && (
          <span className="text-terminal-muted">
            {Object.entries(metric.sub_values)
              .map(([k, v]) => `${k}: ${formatValue(v, k)}`)
              .join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/charts/EcosystemCard.tsx
git commit -m "feat: add EcosystemCard component for live supplementary metrics"
```

---

## Task 19: Frontend — ScoredFactors Component

**Files:**
- Create: `frontend/src/components/charts/ScoredFactors.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/charts/ScoredFactors.tsx
import type { CorrelationFactor } from "../../types/pulse";

interface ScoredFactorsProps {
  factors: CorrelationFactor[];
}

export default function ScoredFactors({ factors }: ScoredFactorsProps) {
  const scored = factors.filter((f) => f.in_score);
  if (scored.length === 0) return null;

  return (
    <div className="bg-terminal-card border border-terminal-border p-4">
      <h3 className="text-sm font-bold text-terminal-accent mb-3 uppercase tracking-wider">
        Scored Factors
      </h3>
      <div className="space-y-3">
        {scored.map((f) => (
          <div key={f.name} className="flex items-center justify-between text-xs">
            <div>
              <div className="text-terminal-text font-medium">{f.label}</div>
              <div className="text-terminal-muted">
                r = {f.correlation > 0 ? "+" : ""}
                {f.correlation.toFixed(3)} · lag {f.optimal_lag_days}d
              </div>
            </div>
            <div className="text-right">
              <div className="text-terminal-text">
                {(f.weight * 100).toFixed(1)}% weight
              </div>
              <div className={f.correlation > 0 ? "text-terminal-green" : "text-terminal-red"}>
                {f.correlation > 0 ? "Bullish signal" : "Bearish signal"}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/charts/ScoredFactors.tsx
git commit -m "feat: add ScoredFactors component with correlation transparency"
```

---

## Task 20: Frontend — Rewrite Pulse Page

**Files:**
- Modify: `frontend/src/pages/Pulse.tsx` (complete rewrite)
- Remove: `frontend/src/components/charts/TimeSeriesChart.tsx`
- Remove: `frontend/src/components/scores/ScoreCard.tsx`
- Remove: `frontend/src/components/scores/FactorBreakdown.tsx`

- [ ] **Step 1: Rewrite Pulse.tsx**

```tsx
// frontend/src/pages/Pulse.tsx
import { useState, useEffect, useCallback, useRef } from "react";
import type { IChartApi } from "lightweight-charts";
import PageLayout from "../components/layout/PageLayout";
import CandlestickChart, { type CandlestickChartHandle } from "../components/charts/CandlestickChart";
import ScoreLine, { type ScoreLineHandle } from "../components/charts/ScoreLine";
import RangeSelector from "../components/charts/RangeSelector";
import EcosystemCard from "../components/charts/EcosystemCard";
import ScoredFactors from "../components/charts/ScoredFactors";
import { fetchChart, fetchCorrelations, fetchEcosystem } from "../api/pulse";
import type { ChartData, CorrelationsData, EcosystemData, ChartRange } from "../types/pulse";

export default function Pulse() {
  const [range, setRange] = useState<ChartRange>("30d");
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [correlations, setCorrelations] = useState<CorrelationsData | null>(null);
  const [ecosystem, setEcosystem] = useState<EcosystemData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Chart refs for bidirectional crosshair sync
  const candleChartRef = useRef<CandlestickChartHandle>(null);
  const scoreLineRef = useRef<ScoreLineHandle>(null);
  const [candleChart, setCandleChart] = useState<IChartApi | null>(null);
  const [scoreChart, setScoreChart] = useState<IChartApi | null>(null);

  // Load chart data when range changes
  const loadChart = useCallback(async (r: ChartRange) => {
    try {
      const data = await fetchChart(r);
      setChartData(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load chart");
    }
  }, []);

  // Initial load: chart + correlations + ecosystem in parallel
  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const [chart, corr, eco] = await Promise.all([
          fetchChart(range),
          fetchCorrelations(),
          fetchEcosystem(),
        ]);
        setChartData(chart);
        setCorrelations(corr);
        setEcosystem(eco);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Get chart refs after mount for bidirectional crosshair sync
  useEffect(() => {
    if (candleChartRef.current) {
      setCandleChart(candleChartRef.current.getChart());
    }
    if (scoreLineRef.current) {
      setScoreChart(scoreLineRef.current.getChart());
    }
  }, [chartData]);

  // Poll ecosystem every 30s
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const eco = await fetchEcosystem();
        setEcosystem(eco);
      } catch {
        // Silently ignore poll failures
      }
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // Range change handler
  const handleRangeChange = useCallback(
    (r: ChartRange) => {
      setRange(r);
      loadChart(r);
    },
    [loadChart]
  );

  // Current score from latest data point
  const currentScore = chartData?.scores?.length
    ? chartData.scores[chartData.scores.length - 1].score
    : null;

  return (
    <PageLayout title="Solana Market Pulse">
      {/* Header with score and range selector */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          {currentScore !== null && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-terminal-muted uppercase">Health</span>
              <span
                className={`text-2xl font-bold ${
                  currentScore >= 70
                    ? "text-terminal-green"
                    : currentScore <= 30
                      ? "text-terminal-red"
                      : "text-terminal-accent"
                }`}
              >
                {currentScore.toFixed(0)}
              </span>
            </div>
          )}
        </div>
        <RangeSelector selected={range} onChange={handleRangeChange} />
      </div>

      {/* Candlestick Chart + Score Line (synced crosshair) */}
      {chartData && chartData.candles.length > 0 && (
        <>
          <CandlestickChart
            ref={candleChartRef}
            candles={chartData.candles}
            scores={chartData.scores}
            height={400}
            syncedChart={scoreChart}
          />
          <ScoreLine
            ref={scoreLineRef}
            scores={chartData.scores}
            height={150}
            syncedChart={candleChart}
          />
        </>
      )}

      {loading && !chartData && (
        <div className="text-terminal-muted text-center py-16">Loading chart data...</div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}

      {/* Scored Factors */}
      {correlations && (
        <div className="mt-6">
          <ScoredFactors factors={correlations.factors} />
        </div>
      )}

      {/* Ecosystem Cards */}
      {ecosystem && ecosystem.metrics.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs text-terminal-muted uppercase tracking-wider mb-3">
            Ecosystem Snapshot
          </h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {ecosystem.metrics.map((m) => (
              <EcosystemCard key={m.name} metric={m} />
            ))}
          </div>
        </div>
      )}
    </PageLayout>
  );
}
```

- [ ] **Step 2: Remove replaced components**

```bash
rm frontend/src/components/charts/TimeSeriesChart.tsx
rm frontend/src/components/scores/ScoreCard.tsx
rm frontend/src/components/scores/FactorBreakdown.tsx
```

- [ ] **Step 3: Clean up old types**

Remove the old `PulseData`, `CompositeScore`, and related interfaces from `frontend/src/types/api.ts` that are no longer used. Keep `MetricValue`, `SourceStatus`, and `HealthResponse` as they're used by the health endpoint.

Edit `frontend/src/types/api.ts` to remove:
- `ScoreFactor` interface
- `CompositeScore` interface
- `PulseData` interface

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Pulse.tsx frontend/src/types/api.ts
git rm frontend/src/components/charts/TimeSeriesChart.tsx
git rm frontend/src/components/scores/FactorBreakdown.tsx
git rm frontend/src/components/scores/ScoreCard.tsx
git commit -m "feat: rewrite Pulse page with candlestick chart and data-driven health score"
```

---

## Task 21: End-to-End Smoke Test

**Files:** None new — verify everything works together.

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: No TypeScript errors, build succeeds

- [ ] **Step 3: Start backend and verify endpoints**

Run: `cd backend && .venv/Scripts/uvicorn app.main:app --port 8000`

Then test endpoints:
```bash
curl http://localhost:8000/api/pulse/chart?range=30d
curl http://localhost:8000/api/pulse/correlations
curl http://localhost:8000/api/pulse/ecosystem
```

Expected: All return valid JSON.

- [ ] **Step 4: Start frontend and verify page loads**

Run: `cd frontend && npm run dev`

Open `http://localhost:5173/pulse` in browser. Verify:
- Candlestick chart renders with SOL price data
- Health score line chart appears below
- Range selector works (30D, 90D, 1Y, All)
- Ecosystem cards show live metrics
- Scored factors section shows correlation info

- [ ] **Step 5: Commit any fixes**

If any issues found during smoke test, fix and commit:
```bash
git add -A
git commit -m "fix: address smoke test issues"
```
