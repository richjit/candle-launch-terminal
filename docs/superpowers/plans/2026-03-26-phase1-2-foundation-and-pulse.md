# Phase 1-2: Foundation + Solana Market Pulse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend foundation (FastAPI, database, cache, scheduler) and frontend skeleton (Vite, routing, dark theme), then deliver the first working tool — Solana Market Pulse — with real data, composite scoring, and a polished dark terminal UI.

**Architecture:** React frontend (Vite + TypeScript + TailwindCSS + Recharts) talks to a Python FastAPI backend via REST. Backend fetchers run on APScheduler intervals, writing to SQLite. Routers read from the DB. An in-memory cache sits in front of external APIs. Each fetcher has retry + circuit breaker resilience.

**Tech Stack:** Python 3.11+ (FastAPI, APScheduler, httpx, SQLAlchemy), Node.js 18+ (Vite, React, TypeScript, TailwindCSS, Recharts, React Router)

**Spec:** `docs/superpowers/specs/2026-03-26-candle-launch-terminal-design.md`

---

## File Map

### Backend Files (Phase 1 — Foundation)

| File | Responsibility |
|---|---|
| `backend/requirements.txt` | Python dependencies |
| `backend/.env.example` | Env var template |
| `backend/app/__init__.py` | Package init |
| `backend/app/main.py` | FastAPI app, CORS, lifespan (scheduler start/stop), router mounting |
| `backend/app/config.py` | Settings via pydantic-settings: API keys, fetch intervals, DB path |
| `backend/app/database.py` | SQLAlchemy async engine, session factory, Base model, `metric_data` table |
| `backend/app/cache.py` | In-memory cache with TTL + per-source rate limiter |
| `backend/app/scheduler.py` | APScheduler setup, job registration |
| `backend/app/resilience.py` | Retry decorator with exponential backoff + jitter, circuit breaker |
| `backend/app/routers/__init__.py` | Package init |
| `backend/app/fetchers/__init__.py` | Package init |
| `backend/app/fetchers/base.py` | BaseFetcher abstract class — fetch/parse/store pattern |
| `backend/app/fetchers/dexscreener.py` | DexScreener fetcher (Phase 1 proof of concept) |
| `backend/app/analysis/__init__.py` | Package init |

### Backend Files (Phase 2 — Pulse Fetchers + Analysis)

| File | Responsibility |
|---|---|
| `backend/app/fetchers/solana_rpc.py` | TPS, priority fees, stablecoin supply via Solana RPC |
| `backend/app/fetchers/coingecko.py` | SOL price, market data |
| `backend/app/fetchers/defillama.py` | TVL, DEX volume, fees, bridges, stablecoins |
| `backend/app/fetchers/fear_greed.py` | Fear & Greed Index |
| `backend/app/fetchers/google_trends.py` | pytrends wrapper |
| `backend/app/analysis/zscore.py` | Z-score anomaly detection |
| `backend/app/analysis/moving_averages.py` | MA crossovers |
| `backend/app/analysis/scores.py` | Composite Health Score calculation |
| `backend/app/routers/pulse.py` | /api/pulse endpoints |
| `backend/app/routers/health.py` | /api/health — data source status |

### Frontend Files (Phase 1 — Skeleton)

| File | Responsibility |
|---|---|
| `frontend/package.json` | Dependencies and scripts |
| `frontend/tsconfig.json` | TypeScript config |
| `frontend/vite.config.ts` | Vite config with proxy to backend |
| `frontend/tailwind.config.ts` | Tailwind with custom dark terminal theme |
| `frontend/postcss.config.js` | PostCSS for Tailwind |
| `frontend/index.html` | Entry HTML |
| `frontend/src/main.tsx` | React entry point |
| `frontend/src/App.tsx` | Router setup, theme provider |
| `frontend/src/styles/globals.css` | Tailwind imports + terminal theme base |
| `frontend/src/types/api.ts` | TypeScript interfaces for API responses |
| `frontend/src/api/client.ts` | Fetch wrapper with base URL, error handling |
| `frontend/src/hooks/useApiPolling.ts` | Hook for polling backend at intervals |
| `frontend/src/hooks/useTheme.ts` | Theme context (terminal vs bloomberg) |
| `frontend/src/components/layout/Sidebar.tsx` | Navigation sidebar |
| `frontend/src/components/layout/PageLayout.tsx` | Standard page wrapper |
| `frontend/src/pages/Pulse.tsx` | Placeholder (Phase 1), full page (Phase 2) |

### Frontend Files (Phase 2 — Pulse UI)

| File | Responsibility |
|---|---|
| `frontend/src/api/pulse.ts` | Pulse API client functions |
| `frontend/src/components/scores/ScoreCard.tsx` | Composite score display with color coding |
| `frontend/src/components/scores/FactorBreakdown.tsx` | Expandable factor list |
| `frontend/src/components/charts/TimeSeriesChart.tsx` | Reusable line chart |
| `frontend/src/components/charts/MetricCard.tsx` | Single metric with value + trend |
| `frontend/src/components/common/StatusBadge.tsx` | Live/Stale/Unavailable indicator |
| `frontend/src/components/common/LastUpdated.tsx` | Timestamp with pulse animation |

### Test Files

| File | Tests |
|---|---|
| `backend/tests/__init__.py` | Package init |
| `backend/tests/conftest.py` | Shared fixtures (test DB, mock HTTP) |
| `backend/tests/test_config.py` | Config loading |
| `backend/tests/test_cache.py` | Cache TTL and rate limiter |
| `backend/tests/test_resilience.py` | Retry + circuit breaker |
| `backend/tests/test_database.py` | DB read/write |
| `backend/tests/test_dexscreener.py` | DexScreener fetcher parsing |
| `backend/tests/test_solana_rpc.py` | Solana RPC fetcher parsing |
| `backend/tests/test_coingecko.py` | CoinGecko fetcher parsing |
| `backend/tests/test_defillama.py` | DeFi Llama fetcher parsing |
| `backend/tests/test_fear_greed.py` | Fear & Greed fetcher parsing |
| `backend/tests/test_google_trends.py` | Google Trends fetcher parsing |
| `backend/tests/test_zscore.py` | Z-score analysis |
| `backend/tests/test_moving_averages.py` | Moving average analysis |
| `backend/tests/test_scores.py` | Composite score calculation |
| `backend/tests/test_pulse_router.py` | Pulse API endpoint responses |

---

## Phase 1: Foundation

### Task 1: Backend Project Setup

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.*
uvicorn[standard]==0.34.*
sqlalchemy[asyncio]==2.0.*
aiosqlite==0.20.*
httpx==0.28.*
apscheduler==3.11.*
pydantic-settings==2.7.*
pytrends==4.9.*
python-dotenv==1.0.*
pytest==8.3.*
pytest-asyncio==0.25.*
pytest-httpx==0.35.*
respx==0.22.*
```

- [ ] **Step 2: Create .env.example**

```
# Solana RPC — free key from helius.dev (optional, falls back to public RPC)
HELIUS_API_KEY=

# CoinGecko — demo key from coingecko.com (optional)
COINGECKO_API_KEY=

# GitHub — personal access token for higher rate limits (optional)
GITHUB_TOKEN=
```

- [ ] **Step 3: Write failing test for config**

```python
# backend/tests/test_config.py
from app.config import Settings

def test_settings_defaults():
    settings = Settings()
    assert settings.database_url == "sqlite+aiosqlite:///./candle.db"
    assert settings.solana_rpc_url == "https://api.mainnet-beta.solana.com"
    assert settings.fetch_interval_rpc == 120
    assert settings.fetch_interval_dexscreener == 60
    assert settings.fetch_interval_defillama == 300
    assert settings.fetch_interval_coingecko == 300
    assert settings.fetch_interval_fear_greed == 3600
    assert settings.fetch_interval_google_trends == 3600

def test_settings_helius_rpc_url():
    settings = Settings(helius_api_key="test-key")
    assert "test-key" in settings.solana_rpc_url
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 5: Create __init__.py files**

```python
# backend/app/__init__.py
# (empty)
```

```python
# backend/tests/__init__.py
# (empty)
```

- [ ] **Step 6: Implement config.py**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./candle.db"

    # API Keys (all optional)
    helius_api_key: str = ""
    coingecko_api_key: str = ""
    github_token: str = ""

    # Solana RPC
    @property
    def solana_rpc_url(self) -> str:
        if self.helius_api_key:
            return f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"
        return "https://api.mainnet-beta.solana.com"

    # Fetch intervals (seconds)
    fetch_interval_rpc: int = 120
    fetch_interval_dexscreener: int = 60
    fetch_interval_defillama: int = 300
    fetch_interval_coingecko: int = 300
    fetch_interval_fear_greed: int = 3600
    fetch_interval_google_trends: int = 3600
    fetch_interval_github: int = 21600

    # Stale data thresholds (seconds)
    stale_threshold_rpc: int = 300
    stale_threshold_dexscreener: int = 300
    stale_threshold_defillama: int = 1800
    stale_threshold_coingecko: int = 1800
    stale_threshold_fear_greed: int = 7200
    stale_threshold_google_trends: int = 21600

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

- [ ] **Step 7: Create conftest.py with shared fixtures**

```python
# backend/tests/conftest.py
import pytest
from app.config import Settings

@pytest.fixture
def test_settings():
    return Settings(
        database_url="sqlite+aiosqlite:///./test_candle.db",
        helius_api_key="",
    )
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/.env.example backend/app/__init__.py backend/app/config.py backend/tests/__init__.py backend/tests/conftest.py backend/tests/test_config.py
git commit -m "feat: backend project setup with config and env template"
```

---

### Task 2: Database Layer

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/tests/test_database.py`

- [ ] **Step 1: Write failing test for database**

```python
# backend/tests/test_database.py
import pytest
import asyncio
from datetime import datetime, timezone
from app.database import init_db, get_session, MetricData

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

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

        from sqlalchemy import select
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

        from sqlalchemy import select
        result = await session.execute(
            select(MetricData)
            .where(MetricData.source == "sol_rpc", MetricData.metric_name == "tps")
            .order_by(MetricData.fetched_at.desc())
            .limit(1)
        )
        latest = result.scalar_one()
        assert latest.value == 30.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_database.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.database'`

- [ ] **Step 3: Implement database.py**

```python
# backend/app/database.py
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Text, Integer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MetricData(Base):
    __tablename__ = "metric_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


async def init_db(database_url: str):
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@asynccontextmanager
async def get_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_database.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py backend/tests/test_database.py
git commit -m "feat: database layer with MetricData model and async session"
```

---

### Task 3: Cache & Rate Limiter

**Files:**
- Create: `backend/app/cache.py`
- Create: `backend/tests/test_cache.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_cache.py
import time
from app.cache import MemoryCache, RateLimiter

def test_cache_set_and_get():
    cache = MemoryCache()
    cache.set("key1", {"data": 42}, ttl=60)
    assert cache.get("key1") == {"data": 42}

def test_cache_expired():
    cache = MemoryCache()
    cache.set("key1", "value", ttl=0)
    time.sleep(0.01)
    assert cache.get("key1") is None

def test_cache_miss():
    cache = MemoryCache()
    assert cache.get("nonexistent") is None

def test_rate_limiter_allows():
    limiter = RateLimiter(max_calls=5, period=1.0)
    for _ in range(5):
        assert limiter.allow("source_a") is True

def test_rate_limiter_blocks():
    limiter = RateLimiter(max_calls=2, period=1.0)
    assert limiter.allow("source_a") is True
    assert limiter.allow("source_a") is True
    assert limiter.allow("source_a") is False

def test_rate_limiter_independent_sources():
    limiter = RateLimiter(max_calls=1, period=1.0)
    assert limiter.allow("source_a") is True
    assert limiter.allow("source_b") is True
    assert limiter.allow("source_a") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement cache.py**

```python
# backend/app/cache.py
import time
from threading import Lock


class MemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: object, ttl: int):
        with self._lock:
            self._store[key] = (time.time() + ttl, value)

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)


class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self._max_calls = max_calls
        self._period = period
        self._calls: dict[str, list[float]] = {}
        self._lock = Lock()

    def allow(self, source: str) -> bool:
        now = time.time()
        with self._lock:
            if source not in self._calls:
                self._calls[source] = []
            # Remove expired timestamps
            self._calls[source] = [t for t in self._calls[source] if now - t < self._period]
            if len(self._calls[source]) >= self._max_calls:
                return False
            self._calls[source].append(now)
            return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_cache.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/cache.py backend/tests/test_cache.py
git commit -m "feat: in-memory cache with TTL and per-source rate limiter"
```

---

### Task 4: Resilience Layer (Retry + Circuit Breaker)

**Files:**
- Create: `backend/app/resilience.py`
- Create: `backend/tests/test_resilience.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_resilience.py
import pytest
from app.resilience import retry_with_backoff, CircuitBreaker, CircuitOpenError

@pytest.mark.asyncio
async def test_retry_succeeds_on_first_try():
    call_count = 0
    @retry_with_backoff(max_retries=3, base_delay=0.01)
    async def always_works():
        nonlocal call_count
        call_count += 1
        return "ok"
    result = await always_works()
    assert result == "ok"
    assert call_count == 1

@pytest.mark.asyncio
async def test_retry_succeeds_after_failures():
    call_count = 0
    @retry_with_backoff(max_retries=3, base_delay=0.01)
    async def fails_twice():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("fail")
        return "ok"
    result = await fails_twice()
    assert result == "ok"
    assert call_count == 3

@pytest.mark.asyncio
async def test_retry_exhausted():
    @retry_with_backoff(max_retries=2, base_delay=0.01)
    async def always_fails():
        raise ConnectionError("fail")
    with pytest.raises(ConnectionError):
        await always_fails()

def test_circuit_breaker_opens_after_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    for _ in range(3):
        cb.record_failure()
    assert cb.is_open is True

def test_circuit_breaker_allows_when_closed():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    cb.record_failure()
    assert cb.is_open is False

def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.is_open is False
    assert cb._failure_count == 0

def test_circuit_open_error():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=300)
    cb.record_failure()
    with pytest.raises(CircuitOpenError):
        cb.check()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_resilience.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement resilience.py**

```python
# backend/app/resilience.py
import asyncio
import random
import time
import functools
import logging

logger = logging.getLogger(__name__)


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 300):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._is_open = False

    @property
    def is_open(self) -> bool:
        if self._is_open and (time.time() - self._last_failure_time > self._recovery_timeout):
            self._is_open = False
            self._failure_count = 0
        return self._is_open

    def check(self):
        if self.is_open:
            raise CircuitOpenError(
                f"Circuit open — {self._recovery_timeout}s recovery, "
                f"last failure {time.time() - self._last_failure_time:.0f}s ago"
            )

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self._failure_threshold:
            self._is_open = True
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} failures")

    def record_success(self):
        self._failure_count = 0
        self._is_open = False


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (4 ** attempt) + random.uniform(0, base_delay)
                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_resilience.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/resilience.py backend/tests/test_resilience.py
git commit -m "feat: retry with backoff and circuit breaker resilience layer"
```

---

### Task 5: Base Fetcher Pattern

**Files:**
- Create: `backend/app/fetchers/__init__.py`
- Create: `backend/app/fetchers/base.py`

- [ ] **Step 1: Create base fetcher (no test needed — abstract class)**

```python
# backend/app/fetchers/__init__.py
# (empty)
```

```python
# backend/app/fetchers/base.py
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx

from app.cache import MemoryCache
from app.resilience import CircuitBreaker, CircuitOpenError, retry_with_backoff

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    """Base class for all data source fetchers.

    Subclasses implement `source_name`, `fetch_data`, and `parse_response`.
    The `run` method handles the full cycle: check circuit → fetch → parse → store.
    """

    def __init__(self, cache: MemoryCache, http_client: httpx.AsyncClient):
        self.cache = cache
        self.http = http_client
        self.circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=300)
        self.last_fetch_at: datetime | None = None
        self.error_count: int = 0

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source."""

    @abstractmethod
    async def fetch_data(self) -> dict:
        """Fetch raw data from the external API. Returns parsed JSON."""

    @abstractmethod
    def parse_response(self, data: dict) -> list[dict]:
        """Parse raw API response into list of metric dicts.

        Each dict: {"metric_name": str, "value": float, "metadata": dict | None}
        """

    async def run(self) -> list[dict]:
        """Full fetch cycle: circuit check → fetch → parse → cache."""
        try:
            self.circuit.check()
        except CircuitOpenError as e:
            logger.warning(f"[{self.source_name}] {e}")
            return []

        try:
            raw_data = await self.fetch_data()
            metrics = self.parse_response(raw_data)
            now = datetime.now(timezone.utc)
            self.last_fetch_at = now
            self.error_count = 0
            self.circuit.record_success()

            # Cache each metric
            for m in metrics:
                cache_key = f"{self.source_name}:{m['metric_name']}"
                self.cache.set(cache_key, {**m, "fetched_at": now.isoformat()}, ttl=600)

            logger.info(f"[{self.source_name}] Fetched {len(metrics)} metrics")
            return metrics

        except Exception as e:
            self.error_count += 1
            self.circuit.record_failure()
            logger.error(f"[{self.source_name}] Fetch failed: {e}")
            return []

    def status(self) -> dict:
        """Return current fetcher health status."""
        return {
            "source": self.source_name,
            "last_fetch_at": self.last_fetch_at.isoformat() if self.last_fetch_at else None,
            "error_count": self.error_count,
            "circuit_open": self.circuit.is_open,
        }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/fetchers/__init__.py backend/app/fetchers/base.py
git commit -m "feat: base fetcher abstract class with circuit breaker integration"
```

---

### Task 6: DexScreener Fetcher (End-to-End Proof)

**Files:**
- Create: `backend/app/fetchers/dexscreener.py`
- Create: `backend/tests/test_dexscreener.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_dexscreener.py
import pytest
import httpx
from unittest.mock import AsyncMock
from app.cache import MemoryCache
from app.fetchers.dexscreener import DexScreenerFetcher

MOCK_RESPONSE = {
    "pairs": [
        {
            "chainId": "solana",
            "baseToken": {"symbol": "BONK", "name": "Bonk"},
            "quoteToken": {"symbol": "SOL"},
            "priceUsd": "0.00001234",
            "volume": {"h24": 5000000},
            "liquidity": {"usd": 2000000},
            "priceChange": {"h24": 15.5},
            "fdv": 800000000,
            "pairAddress": "ABC123",
        }
    ]
}

@pytest.fixture
def fetcher():
    cache = MemoryCache()
    client = httpx.AsyncClient()
    return DexScreenerFetcher(cache=cache, http_client=client)

def test_parse_response(fetcher):
    metrics = fetcher.parse_response(MOCK_RESPONSE)
    names = {m["metric_name"] for m in metrics}
    assert "top_pairs" in names
    top_pairs = next(m for m in metrics if m["metric_name"] == "top_pairs")
    assert len(top_pairs["metadata"]["pairs"]) == 1
    assert top_pairs["metadata"]["pairs"][0]["symbol"] == "BONK"
    assert top_pairs["metadata"]["pairs"][0]["price_usd"] == 0.00001234
    assert top_pairs["metadata"]["pairs"][0]["volume_24h"] == 5000000

def test_source_name(fetcher):
    assert fetcher.source_name == "dexscreener"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_dexscreener.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement DexScreener fetcher**

```python
# backend/app/fetchers/dexscreener.py
from app.fetchers.base import BaseFetcher
from app.resilience import retry_with_backoff


class DexScreenerFetcher(BaseFetcher):
    BASE_URL = "https://api.dexscreener.com/latest/dex"

    @property
    def source_name(self) -> str:
        return "dexscreener"

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_data(self) -> dict:
        resp = await self.http.get(
            f"{self.BASE_URL}/tokens/So11111111111111111111111111111111111111112",
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()

    def parse_response(self, data: dict) -> list[dict]:
        pairs = data.get("pairs") or []
        parsed_pairs = []
        for p in pairs[:20]:  # Top 20 pairs
            parsed_pairs.append({
                "symbol": p.get("baseToken", {}).get("symbol", ""),
                "name": p.get("baseToken", {}).get("name", ""),
                "price_usd": float(p.get("priceUsd") or 0),
                "volume_24h": float(p.get("volume", {}).get("h24") or 0),
                "liquidity_usd": float(p.get("liquidity", {}).get("usd") or 0),
                "price_change_24h": float(p.get("priceChange", {}).get("h24") or 0),
                "fdv": float(p.get("fdv") or 0),
                "pair_address": p.get("pairAddress", ""),
            })

        total_volume = sum(p["volume_24h"] for p in parsed_pairs)

        return [
            {
                "metric_name": "top_pairs",
                "value": total_volume,
                "metadata": {"pairs": parsed_pairs},
            },
            {
                "metric_name": "sol_total_volume_24h",
                "value": total_volume,
                "metadata": None,
            },
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_dexscreener.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/fetchers/dexscreener.py backend/tests/test_dexscreener.py
git commit -m "feat: DexScreener fetcher with SOL pair data parsing"
```

---

### Task 7: Scheduler + FastAPI App

**Files:**
- Create: `backend/app/scheduler.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/health.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create scheduler.py**

```python
# backend/app/scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def register_fetcher_job(fetcher, interval_seconds: int):
    """Register a fetcher to run on a fixed interval."""
    job_id = f"fetch_{fetcher.source_name}"
    scheduler.add_job(
        fetcher.run,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id=job_id,
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Registered job {job_id} every {interval_seconds}s")
```

- [ ] **Step 2: Create health router**

```python
# backend/app/routers/__init__.py
# (empty)
```

```python
# backend/app/routers/health.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])

# Will be populated with fetcher references at app startup
_fetchers: list = []


def set_fetchers(fetchers: list):
    global _fetchers
    _fetchers = fetchers


@router.get("")
async def health():
    return {
        "status": "ok",
        "sources": [f.status() for f in _fetchers],
    }
```

- [ ] **Step 3: Create main.py**

```python
# backend/app/main.py
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache import MemoryCache
from app.config import settings
from app.database import init_db
from app.scheduler import scheduler, register_fetcher_job
from app.fetchers.dexscreener import DexScreenerFetcher
from app.routers.health import router as health_router, set_fetchers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

cache = MemoryCache()
http_client: httpx.AsyncClient | None = None
db_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, db_engine

    # Startup
    db_engine = await init_db(settings.database_url)
    http_client = httpx.AsyncClient()

    # Create fetchers
    dexscreener = DexScreenerFetcher(cache=cache, http_client=http_client)

    all_fetchers = [dexscreener]
    set_fetchers(all_fetchers)

    # Register scheduled jobs
    register_fetcher_job(dexscreener, settings.fetch_interval_dexscreener)

    # Run initial fetch
    for f in all_fetchers:
        await f.run()

    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
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
```

- [ ] **Step 4: Verify backend starts**

Run: `cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --port 8000`
Expected: Server starts, initial DexScreener fetch logged, no errors. Hit `http://localhost:8000/api/health` to verify JSON response.

- [ ] **Step 5: Commit**

```bash
git add backend/app/scheduler.py backend/app/routers/__init__.py backend/app/routers/health.py backend/app/main.py
git commit -m "feat: FastAPI app with scheduler, CORS, health endpoint, DexScreener job"
```

---

### Task 8: Frontend Skeleton

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles/globals.css`
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: Initialize Vite React-TS project**

Run: `cd frontend && npm create vite@latest . -- --template react-ts` (if directory is empty, otherwise scaffold manually)

If the directory is not empty or scaffolding fails, create the files manually as described below.

- [ ] **Step 2: Install dependencies**

Run: `cd frontend && npm install react-router-dom recharts && npm install -D tailwindcss @tailwindcss/vite`

- [ ] **Step 3: Configure tailwind.config.ts**

```typescript
// frontend/tailwind.config.ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0a0a0f",
          card: "#12121a",
          border: "#1e1e2e",
          accent: "#f0b90b",
          green: "#00e676",
          red: "#ff1744",
          cyan: "#00e5ff",
          muted: "#6b7280",
          text: "#e0e0e0",
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 4: Configure vite.config.ts with API proxy**

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 5: Create globals.css**

```css
/* frontend/src/styles/globals.css */
@import "tailwindcss";

@theme {
  --color-terminal-bg: #0a0a0f;
  --color-terminal-card: #12121a;
  --color-terminal-border: #1e1e2e;
  --color-terminal-accent: #f0b90b;
  --color-terminal-green: #00e676;
  --color-terminal-red: #ff1744;
  --color-terminal-cyan: #00e5ff;
  --color-terminal-muted: #6b7280;
  --color-terminal-text: #e0e0e0;

  --font-mono: "JetBrains Mono", "IBM Plex Mono", monospace;
}

body {
  background-color: var(--color-terminal-bg);
  color: var(--color-terminal-text);
  font-family: var(--font-mono);
  margin: 0;
}
```

- [ ] **Step 6: Create main.tsx entry**

```tsx
// frontend/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
```

- [ ] **Step 7: Create App.tsx with routing**

```tsx
// frontend/src/App.tsx
import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import Pulse from "./pages/Pulse";

export default function App() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <Routes>
          <Route path="/" element={<Navigate to="/pulse" replace />} />
          <Route path="/pulse" element={<Pulse />} />
        </Routes>
      </main>
    </div>
  );
}
```

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: frontend skeleton with Vite, React Router, TailwindCSS terminal theme"
```

---

### Task 9: Sidebar + Page Layout Components

**Files:**
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/components/layout/PageLayout.tsx`
- Create: `frontend/src/pages/Pulse.tsx` (placeholder)

- [ ] **Step 1: Create Sidebar**

```tsx
// frontend/src/components/layout/Sidebar.tsx
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/pulse", label: "Pulse" },
  { to: "/launch", label: "Launch" },
  { to: "/narrative", label: "Narrative" },
  { to: "/whales", label: "Whales" },
  { to: "/chains", label: "Chains" },
  { to: "/trending", label: "Trending" },
];

export default function Sidebar() {
  return (
    <nav className="w-48 h-screen bg-terminal-card border-r border-terminal-border flex flex-col p-4 shrink-0">
      <div className="text-terminal-accent font-bold text-lg mb-8 tracking-wider">
        CANDLE
      </div>
      <ul className="space-y-1 flex-1">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `block px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "text-terminal-accent bg-terminal-accent/10 border-l-2 border-terminal-accent"
                    : "text-terminal-muted hover:text-terminal-text"
                }`
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="border-t border-terminal-border pt-4">
        <NavLink
          to="/settings"
          className="block px-3 py-2 text-sm text-terminal-muted hover:text-terminal-text"
        >
          Settings
        </NavLink>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: Create PageLayout**

```tsx
// frontend/src/components/layout/PageLayout.tsx
import { ReactNode } from "react";

interface PageLayoutProps {
  title: string;
  children: ReactNode;
}

export default function PageLayout({ title, children }: PageLayoutProps) {
  return (
    <div className="max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-terminal-accent mb-6">{title}</h1>
      {children}
    </div>
  );
}
```

- [ ] **Step 3: Create Pulse placeholder page**

```tsx
// frontend/src/pages/Pulse.tsx
import PageLayout from "../components/layout/PageLayout";

export default function Pulse() {
  return (
    <PageLayout title="Solana Market Pulse">
      <div className="text-terminal-muted">Loading pulse data...</div>
    </PageLayout>
  );
}
```

- [ ] **Step 4: Verify frontend runs**

Run: `cd frontend && npm run dev`
Expected: Opens on `http://localhost:5173`, shows dark background with sidebar and "Solana Market Pulse" heading.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ frontend/src/pages/
git commit -m "feat: sidebar navigation, page layout, and pulse placeholder"
```

---

### Task 10: API Client + useApiPolling Hook

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/hooks/useApiPolling.ts`
- Create: `frontend/src/types/api.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/types/api.ts
export interface MetricValue {
  metric_name: string;
  value: number;
  metadata: Record<string, unknown> | null;
  fetched_at: string;
}

export interface SourceStatus {
  source: string;
  last_fetch_at: string | null;
  error_count: number;
  circuit_open: boolean;
}

export interface HealthResponse {
  status: string;
  sources: SourceStatus[];
}

export interface ScoreFactor {
  name: string;
  value: number;
  normalized: number; // -1 to +1
  contribution: number;
  label: string;
}

export interface CompositeScore {
  score: number;
  max_score: number;
  factors_available: number;
  factors_total: number;
  factors: ScoreFactor[];
}

export interface PulseData {
  health_score: CompositeScore;
  sol_price: { value: number; change_24h: number; change_7d: number; change_30d: number } | null;
  tps: { current: number; history: Array<{ timestamp: string; value: number }> } | null;
  priority_fees: { current: number; history: Array<{ timestamp: string; value: number }> } | null;
  stablecoin_supply: { total: number; usdc: number; usdt: number } | null;
  dex_volume: { solana: number; ethereum: number; base: number } | null;
  tvl: { current: number; history: Array<{ timestamp: string; value: number }> } | null;
  bridge_flows: { inflow: number; outflow: number; net: number } | null;
  fear_greed: { value: number; label: string } | null;
  google_trends: { solana: number; ethereum: number; bitcoin: number } | null;
  last_updated: string;
}
```

- [ ] **Step 2: Create API client**

```typescript
// frontend/src/api/client.ts
const BASE_URL = "/api";

export async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}
```

- [ ] **Step 3: Create useApiPolling hook**

```typescript
// frontend/src/hooks/useApiPolling.ts
import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "../api/client";

interface UseApiPollingResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refresh: () => void;
}

export function useApiPolling<T>(
  path: string,
  intervalMs: number = 30000
): UseApiPollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const result = await apiFetch<T>(path);
      setData(result);
      setError(null);
      setLastUpdated(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, intervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData, intervalMs]);

  return { data, loading, error, lastUpdated, refresh: fetchData };
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/ frontend/src/api/ frontend/src/hooks/
git commit -m "feat: API client, TypeScript types, and useApiPolling hook"
```

---

### Task 11: .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Create .gitignore at project root**

```
# Backend
backend/.env
backend/venv/
backend/__pycache__/
backend/**/__pycache__/
*.pyc
*.db

# Frontend
frontend/node_modules/
frontend/dist/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore for backend, frontend, and IDE files"
```

---

## Phase 2: Solana Market Pulse

### Task 12: Solana RPC Fetcher

**Files:**
- Create: `backend/app/fetchers/solana_rpc.py`
- Create: `backend/tests/test_solana_rpc.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_solana_rpc.py
import pytest
from app.cache import MemoryCache
from app.fetchers.solana_rpc import SolanaRpcFetcher
import httpx

MOCK_TPS_RESPONSE = {
    "jsonrpc": "2.0",
    "result": [
        {"numTransactions": 2500, "numSlots": 1, "samplePeriodSecs": 60},
        {"numTransactions": 2200, "numSlots": 1, "samplePeriodSecs": 60},
    ],
    "id": 1,
}

MOCK_PRIORITY_FEES_RESPONSE = {
    "jsonrpc": "2.0",
    "result": [
        {"slot": 100, "prioritizationFee": 5000},
        {"slot": 101, "prioritizationFee": 8000},
        {"slot": 102, "prioritizationFee": 3000},
    ],
    "id": 1,
}

MOCK_TOKEN_SUPPLY_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "context": {"slot": 100},
        "value": {"amount": "30000000000000", "decimals": 6, "uiAmount": 30000000.0},
    },
    "id": 1,
}

@pytest.fixture
def fetcher():
    cache = MemoryCache()
    client = httpx.AsyncClient()
    return SolanaRpcFetcher(
        cache=cache,
        http_client=client,
        rpc_url="https://api.mainnet-beta.solana.com",
    )

def test_parse_tps(fetcher):
    metrics = fetcher._parse_tps(MOCK_TPS_RESPONSE)
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "tps"
    assert metrics[0]["value"] == pytest.approx(2350.0)  # average of 2500 and 2200

def test_parse_priority_fees(fetcher):
    metrics = fetcher._parse_priority_fees(MOCK_PRIORITY_FEES_RESPONSE)
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "priority_fees"
    assert metrics[0]["value"] == pytest.approx(5333.33, rel=0.01)  # average

def test_parse_token_supply(fetcher):
    result = fetcher._parse_token_supply(MOCK_TOKEN_SUPPLY_RESPONSE)
    assert result == pytest.approx(30000000.0)

def test_source_name(fetcher):
    assert fetcher.source_name == "solana_rpc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_solana_rpc.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Solana RPC fetcher**

```python
# backend/app/fetchers/solana_rpc.py
import logging
from app.fetchers.base import BaseFetcher
from app.resilience import retry_with_backoff
from app.cache import MemoryCache
import httpx

logger = logging.getLogger(__name__)

# Stablecoin mint addresses on Solana
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


class SolanaRpcFetcher(BaseFetcher):
    def __init__(self, cache: MemoryCache, http_client: httpx.AsyncClient, rpc_url: str):
        super().__init__(cache=cache, http_client=http_client)
        self.rpc_url = rpc_url

    @property
    def source_name(self) -> str:
        return "solana_rpc"

    async def _rpc_call(self, method: str, params: list | None = None) -> dict:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        resp = await self.http.post(self.rpc_url, json=payload, timeout=15.0)
        resp.raise_for_status()
        return resp.json()

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_data(self) -> dict:
        tps_data = await self._rpc_call("getRecentPerformanceSamples", [10])
        fees_data = await self._rpc_call("getRecentPrioritizationFees")
        usdc_supply = await self._rpc_call("getTokenSupply", [USDC_MINT])
        usdt_supply = await self._rpc_call("getTokenSupply", [USDT_MINT])
        return {
            "tps": tps_data,
            "priority_fees": fees_data,
            "usdc_supply": usdc_supply,
            "usdt_supply": usdt_supply,
        }

    def parse_response(self, data: dict) -> list[dict]:
        metrics = []
        metrics.extend(self._parse_tps(data["tps"]))
        metrics.extend(self._parse_priority_fees(data["priority_fees"]))

        usdc = self._parse_token_supply(data["usdc_supply"])
        usdt = self._parse_token_supply(data["usdt_supply"])
        metrics.append({
            "metric_name": "stablecoin_supply",
            "value": usdc + usdt,
            "metadata": {"usdc": usdc, "usdt": usdt},
        })
        return metrics

    def _parse_tps(self, data: dict) -> list[dict]:
        samples = data.get("result") or []
        if not samples:
            return []
        avg_tps = sum(s["numTransactions"] / max(s["samplePeriodSecs"], 1) * s["samplePeriodSecs"]
                      for s in samples) / len(samples)
        return [{"metric_name": "tps", "value": avg_tps, "metadata": {"sample_count": len(samples)}}]

    def _parse_priority_fees(self, data: dict) -> list[dict]:
        fees = data.get("result") or []
        if not fees:
            return []
        avg_fee = sum(f["prioritizationFee"] for f in fees) / len(fees)
        return [{"metric_name": "priority_fees", "value": avg_fee, "metadata": {"sample_count": len(fees)}}]

    def _parse_token_supply(self, data: dict) -> float:
        try:
            return float(data["result"]["value"]["uiAmount"] or 0)
        except (KeyError, TypeError):
            return 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_solana_rpc.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/fetchers/solana_rpc.py backend/tests/test_solana_rpc.py
git commit -m "feat: Solana RPC fetcher — TPS, priority fees, stablecoin supply"
```

---

### Task 13: CoinGecko Fetcher

**Files:**
- Create: `backend/app/fetchers/coingecko.py`
- Create: `backend/tests/test_coingecko.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_coingecko.py
import pytest
import httpx
from app.cache import MemoryCache
from app.fetchers.coingecko import CoinGeckoFetcher

MOCK_RESPONSE = {
    "solana": {
        "usd": 145.50,
        "usd_24h_change": 3.2,
        "usd_7d_change": -1.5,
        "usd_30d_change": 12.8,
        "usd_24h_vol": 2500000000,
        "usd_market_cap": 65000000000,
    }
}

@pytest.fixture
def fetcher():
    cache = MemoryCache()
    client = httpx.AsyncClient()
    return CoinGeckoFetcher(cache=cache, http_client=client, api_key="")

def test_parse_response(fetcher):
    metrics = fetcher.parse_response(MOCK_RESPONSE)
    names = {m["metric_name"] for m in metrics}
    assert "sol_price" in names
    price = next(m for m in metrics if m["metric_name"] == "sol_price")
    assert price["value"] == 145.50
    assert price["metadata"]["change_24h"] == 3.2
    assert price["metadata"]["change_7d"] == -1.5
    assert price["metadata"]["change_30d"] == 12.8

def test_source_name(fetcher):
    assert fetcher.source_name == "coingecko"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_coingecko.py -v`
Expected: FAIL

- [ ] **Step 3: Implement CoinGecko fetcher**

```python
# backend/app/fetchers/coingecko.py
from app.fetchers.base import BaseFetcher
from app.resilience import retry_with_backoff
from app.cache import MemoryCache
import httpx


class CoinGeckoFetcher(BaseFetcher):
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, cache: MemoryCache, http_client: httpx.AsyncClient, api_key: str):
        super().__init__(cache=cache, http_client=http_client)
        self.api_key = api_key

    @property
    def source_name(self) -> str:
        return "coingecko"

    @retry_with_backoff(max_retries=3, base_delay=2.0)
    async def fetch_data(self) -> dict:
        headers = {}
        if self.api_key:
            headers["x-cg-demo-api-key"] = self.api_key
        resp = await self.http.get(
            f"{self.BASE_URL}/simple/price",
            params={
                "ids": "solana",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_7d_change": "true",
                "include_30d_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true",
            },
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()

    def parse_response(self, data: dict) -> list[dict]:
        sol = data.get("solana", {})
        return [
            {
                "metric_name": "sol_price",
                "value": float(sol.get("usd", 0)),
                "metadata": {
                    "change_24h": float(sol.get("usd_24h_change", 0)),
                    "change_7d": float(sol.get("usd_7d_change", 0)),
                    "change_30d": float(sol.get("usd_30d_change", 0)),
                    "volume_24h": float(sol.get("usd_24h_vol", 0)),
                    "market_cap": float(sol.get("usd_market_cap", 0)),
                },
            }
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_coingecko.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/fetchers/coingecko.py backend/tests/test_coingecko.py
git commit -m "feat: CoinGecko fetcher — SOL price with 24h/7d/30d changes"
```

---

### Task 14: DeFi Llama Fetcher

**Files:**
- Create: `backend/app/fetchers/defillama.py`
- Create: `backend/tests/test_defillama.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_defillama.py
import pytest
import httpx
from app.cache import MemoryCache
from app.fetchers.defillama import DefiLlamaFetcher

MOCK_TVL_RESPONSE = [
    {"date": 1700000000, "tvl": 4500000000},
    {"date": 1700086400, "tvl": 4600000000},
]

MOCK_DEX_VOLUME_RESPONSE = {
    "totalDataChart": [
        [1700000000, 500000000],
        [1700086400, 600000000],
    ],
    "total24h": 600000000,
}

MOCK_CHAINS_TVL = [
    {"name": "Ethereum", "tvl": 50000000000},
    {"name": "Solana", "tvl": 5000000000},
    {"name": "Base", "tvl": 3000000000},
]

MOCK_BRIDGE_VOLUME = {
    "chains": {
        "Solana": {
            "txs": {"deposit": {"total": 100000000}, "withdraw": {"total": 80000000}},
        }
    }
}

@pytest.fixture
def fetcher():
    cache = MemoryCache()
    client = httpx.AsyncClient()
    return DefiLlamaFetcher(cache=cache, http_client=client)

def test_parse_response(fetcher):
    data = {
        "tvl_history": MOCK_TVL_RESPONSE,
        "dex_volume": MOCK_DEX_VOLUME_RESPONSE,
        "chains_tvl": MOCK_CHAINS_TVL,
    }
    metrics = fetcher.parse_response(data)
    names = {m["metric_name"] for m in metrics}
    assert "solana_tvl" in names
    assert "dex_volume_24h" in names
    assert "chains_tvl" in names

    tvl = next(m for m in metrics if m["metric_name"] == "solana_tvl")
    assert tvl["value"] == 4600000000

    dex_vol = next(m for m in metrics if m["metric_name"] == "dex_volume_24h")
    assert dex_vol["value"] == 600000000

def test_source_name(fetcher):
    assert fetcher.source_name == "defillama"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_defillama.py -v`
Expected: FAIL

- [ ] **Step 3: Implement DeFi Llama fetcher**

```python
# backend/app/fetchers/defillama.py
from app.fetchers.base import BaseFetcher
from app.resilience import retry_with_backoff


class DefiLlamaFetcher(BaseFetcher):
    BASE_URL = "https://api.llama.fi"
    DEX_URL = "https://api.llama.fi/overview/dexs/solana"

    @property
    def source_name(self) -> str:
        return "defillama"

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_data(self) -> dict:
        tvl_resp = await self.http.get(
            f"{self.BASE_URL}/v2/historicalChainTvl/Solana", timeout=15.0
        )
        tvl_resp.raise_for_status()

        dex_resp = await self.http.get(self.DEX_URL, timeout=15.0)
        dex_resp.raise_for_status()

        chains_resp = await self.http.get(f"{self.BASE_URL}/v2/chains", timeout=15.0)
        chains_resp.raise_for_status()

        return {
            "tvl_history": tvl_resp.json(),
            "dex_volume": dex_resp.json(),
            "chains_tvl": chains_resp.json(),
        }

    def parse_response(self, data: dict) -> list[dict]:
        metrics = []

        # Solana TVL (latest)
        tvl_history = data.get("tvl_history") or []
        if tvl_history:
            latest_tvl = tvl_history[-1].get("tvl", 0)
            history = [{"timestamp": h["date"], "value": h["tvl"]} for h in tvl_history[-30:]]
            metrics.append({
                "metric_name": "solana_tvl",
                "value": latest_tvl,
                "metadata": {"history": history},
            })

        # DEX volume
        dex_data = data.get("dex_volume", {})
        vol_24h = dex_data.get("total24h", 0)
        metrics.append({
            "metric_name": "dex_volume_24h",
            "value": float(vol_24h or 0),
            "metadata": None,
        })

        # Cross-chain TVL comparison
        chains = data.get("chains_tvl") or []
        chain_map = {}
        for c in chains:
            name = c.get("name", "")
            if name in ("Ethereum", "Solana", "Base", "Arbitrum", "BSC"):
                chain_map[name] = float(c.get("tvl", 0))
        metrics.append({
            "metric_name": "chains_tvl",
            "value": chain_map.get("Solana", 0),
            "metadata": {"chains": chain_map},
        })

        return metrics
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_defillama.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/fetchers/defillama.py backend/tests/test_defillama.py
git commit -m "feat: DeFi Llama fetcher — TVL, DEX volume, cross-chain comparison"
```

---

### Task 15: Fear & Greed + Google Trends Fetchers

**Files:**
- Create: `backend/app/fetchers/fear_greed.py`
- Create: `backend/app/fetchers/google_trends.py`
- Create: `backend/tests/test_fear_greed.py`
- Create: `backend/tests/test_google_trends.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_fear_greed.py
import pytest
import httpx
from app.cache import MemoryCache
from app.fetchers.fear_greed import FearGreedFetcher

MOCK_RESPONSE = {
    "data": [
        {"value": "25", "value_classification": "Extreme Fear", "timestamp": "1700000000"}
    ]
}

@pytest.fixture
def fetcher():
    return FearGreedFetcher(cache=MemoryCache(), http_client=httpx.AsyncClient())

def test_parse_response(fetcher):
    metrics = fetcher.parse_response(MOCK_RESPONSE)
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "fear_greed"
    assert metrics[0]["value"] == 25
    assert metrics[0]["metadata"]["label"] == "Extreme Fear"

def test_source_name(fetcher):
    assert fetcher.source_name == "fear_greed"
```

```python
# backend/tests/test_google_trends.py
import pytest
import httpx
from app.cache import MemoryCache
from app.fetchers.google_trends import GoogleTrendsFetcher

@pytest.fixture
def fetcher():
    return GoogleTrendsFetcher(cache=MemoryCache(), http_client=httpx.AsyncClient())

def test_parse_response(fetcher):
    # Simulate pytrends-like response
    mock_data = {"solana": 75, "ethereum": 60, "bitcoin": 90}
    metrics = fetcher.parse_response(mock_data)
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "google_trends"
    assert metrics[0]["metadata"]["solana"] == 75
    assert metrics[0]["metadata"]["ethereum"] == 60
    assert metrics[0]["metadata"]["bitcoin"] == 90

def test_source_name(fetcher):
    assert fetcher.source_name == "google_trends"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_fear_greed.py tests/test_google_trends.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Fear & Greed fetcher**

```python
# backend/app/fetchers/fear_greed.py
from app.fetchers.base import BaseFetcher
from app.resilience import retry_with_backoff


class FearGreedFetcher(BaseFetcher):
    URL = "https://api.alternative.me/fng/"

    @property
    def source_name(self) -> str:
        return "fear_greed"

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_data(self) -> dict:
        resp = await self.http.get(self.URL, params={"limit": 1}, timeout=15.0)
        resp.raise_for_status()
        return resp.json()

    def parse_response(self, data: dict) -> list[dict]:
        entries = data.get("data") or []
        if not entries:
            return []
        entry = entries[0]
        return [{
            "metric_name": "fear_greed",
            "value": float(entry.get("value", 0)),
            "metadata": {"label": entry.get("value_classification", "Unknown")},
        }]
```

- [ ] **Step 4: Implement Google Trends fetcher**

```python
# backend/app/fetchers/google_trends.py
import logging
import random
import asyncio
from app.fetchers.base import BaseFetcher

logger = logging.getLogger(__name__)

KEYWORDS = ["solana", "ethereum", "bitcoin"]


class GoogleTrendsFetcher(BaseFetcher):
    @property
    def source_name(self) -> str:
        return "google_trends"

    async def fetch_data(self) -> dict:
        # Run pytrends in a thread to avoid blocking the event loop
        import concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, self._fetch_sync)
        return result

    def _fetch_sync(self) -> dict:
        try:
            from pytrends.request import TrendReq

            # Random delay to avoid rate limiting
            import time
            time.sleep(random.uniform(1, 3))

            pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
            pytrends.build_payload(KEYWORDS, timeframe="now 7-d")
            df = pytrends.interest_over_time()

            if df.empty:
                return {kw: 0 for kw in KEYWORDS}

            # Get the latest values
            latest = df.iloc[-1]
            return {kw: int(latest.get(kw, 0)) for kw in KEYWORDS}
        except Exception as e:
            logger.warning(f"Google Trends fetch failed: {e}")
            return {kw: 0 for kw in KEYWORDS}

    def parse_response(self, data: dict) -> list[dict]:
        # Use solana's value as the primary metric
        solana_val = data.get("solana", 0)
        return [{
            "metric_name": "google_trends",
            "value": float(solana_val),
            "metadata": data,
        }]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_fear_greed.py tests/test_google_trends.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/fetchers/fear_greed.py backend/app/fetchers/google_trends.py backend/tests/test_fear_greed.py backend/tests/test_google_trends.py
git commit -m "feat: Fear & Greed Index and Google Trends fetchers"
```

---

### Task 16: Z-Score + Moving Averages Analysis

**Files:**
- Create: `backend/app/analysis/__init__.py`
- Create: `backend/app/analysis/zscore.py`
- Create: `backend/app/analysis/moving_averages.py`
- Create: `backend/tests/test_zscore.py`
- Create: `backend/tests/test_moving_averages.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_zscore.py
import pytest
from app.analysis.zscore import compute_zscore, classify_zscore

def test_zscore_normal():
    values = [10, 12, 11, 13, 10, 12, 11, 12, 11, 10]
    z = compute_zscore(values, current=12)
    assert -2 < z < 2  # Normal range

def test_zscore_high_anomaly():
    values = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]
    z = compute_zscore(values, current=20)
    assert z > 2

def test_zscore_low_anomaly():
    values = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]
    z = compute_zscore(values, current=0)
    assert z < -2

def test_zscore_insufficient_data():
    z = compute_zscore([10], current=10)
    assert z == 0.0

def test_classify_bullish():
    assert classify_zscore(2.5) == 1

def test_classify_bearish():
    assert classify_zscore(-2.5) == -1

def test_classify_neutral():
    assert classify_zscore(0.5) == 0
```

```python
# backend/tests/test_moving_averages.py
import pytest
from app.analysis.moving_averages import moving_average, detect_crossover

def test_moving_average():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    ma = moving_average(values, window=3)
    assert ma == pytest.approx([2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])

def test_moving_average_insufficient():
    values = [1, 2]
    ma = moving_average(values, window=5)
    assert ma == []

def test_crossover_bullish():
    short_ma = [1, 2, 3, 5, 7]
    long_ma = [2, 3, 4, 4, 4]
    signal = detect_crossover(short_ma, long_ma)
    assert signal == "bullish"

def test_crossover_bearish():
    short_ma = [7, 5, 3, 2, 1]
    long_ma = [4, 4, 4, 3, 3]
    signal = detect_crossover(short_ma, long_ma)
    assert signal == "bearish"

def test_crossover_neutral():
    short_ma = [3, 3, 3]
    long_ma = [3, 3, 3]
    signal = detect_crossover(short_ma, long_ma)
    assert signal == "neutral"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_zscore.py tests/test_moving_averages.py -v`
Expected: FAIL

- [ ] **Step 3: Implement zscore.py**

```python
# backend/app/analysis/__init__.py
# (empty)
```

```python
# backend/app/analysis/zscore.py
import math


def compute_zscore(values: list[float], current: float) -> float:
    """Compute z-score of current value against historical values."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    return (current - mean) / std


def classify_zscore(z: float, threshold: float = 1.5) -> int:
    """Classify z-score as bullish (+1), neutral (0), or bearish (-1).

    For metrics where higher = better (volume, TPS):
      z > threshold → bullish (+1)
      z < -threshold → bearish (-1)
    """
    if z > threshold:
        return 1
    elif z < -threshold:
        return -1
    return 0
```

- [ ] **Step 4: Implement moving_averages.py**

```python
# backend/app/analysis/moving_averages.py


def moving_average(values: list[float], window: int) -> list[float]:
    """Compute simple moving average."""
    if len(values) < window:
        return []
    result = []
    for i in range(len(values) - window + 1):
        window_slice = values[i : i + window]
        result.append(sum(window_slice) / window)
    return result


def detect_crossover(short_ma: list[float], long_ma: list[float]) -> str:
    """Detect crossover between short and long moving averages.

    Returns: "bullish" if short crossed above long recently,
             "bearish" if short crossed below long recently,
             "neutral" otherwise.
    """
    if len(short_ma) < 2 or len(long_ma) < 2:
        return "neutral"

    # Align to same length
    min_len = min(len(short_ma), len(long_ma))
    short = short_ma[-min_len:]
    long_ = long_ma[-min_len:]

    prev_diff = short[-2] - long_[-2]
    curr_diff = short[-1] - long_[-1]

    if prev_diff <= 0 and curr_diff > 0:
        return "bullish"
    elif prev_diff >= 0 and curr_diff < 0:
        return "bearish"
    return "neutral"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_zscore.py tests/test_moving_averages.py -v`
Expected: PASS (11 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/analysis/ backend/tests/test_zscore.py backend/tests/test_moving_averages.py
git commit -m "feat: z-score anomaly detection and moving average crossover analysis"
```

---

### Task 17: Composite Health Score

**Files:**
- Create: `backend/app/analysis/scores.py`
- Create: `backend/tests/test_scores.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_scores.py
import pytest
from app.analysis.scores import compute_health_score, ScoreFactor

def test_health_score_all_bullish():
    factors = [
        ScoreFactor(name="tps", value=3000, z_score=2.0, weight=1.0),
        ScoreFactor(name="priority_fees", value=5000, z_score=1.8, weight=1.0),
        ScoreFactor(name="dex_volume", value=1e9, z_score=2.5, weight=1.5),
        ScoreFactor(name="tvl", value=5e9, z_score=1.0, weight=1.0),
        ScoreFactor(name="stablecoin_supply", value=3e7, z_score=0.5, weight=1.0),
        ScoreFactor(name="fear_greed", value=75, z_score=1.5, weight=0.5),
    ]
    result = compute_health_score(factors)
    assert result.score > 70
    assert result.factors_available == 6
    assert result.factors_total == 6

def test_health_score_all_bearish():
    factors = [
        ScoreFactor(name="tps", value=500, z_score=-2.5, weight=1.0),
        ScoreFactor(name="dex_volume", value=1e7, z_score=-3.0, weight=1.5),
        ScoreFactor(name="tvl", value=2e9, z_score=-2.0, weight=1.0),
    ]
    result = compute_health_score(factors)
    assert result.score < 30

def test_health_score_empty():
    result = compute_health_score([])
    assert result.score == 50  # neutral default
    assert result.factors_available == 0

def test_health_score_clamped():
    factors = [
        ScoreFactor(name="x", value=999, z_score=10.0, weight=5.0),
    ]
    result = compute_health_score(factors)
    assert 0 <= result.score <= 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_scores.py -v`
Expected: FAIL

- [ ] **Step 3: Implement scores.py**

```python
# backend/app/analysis/scores.py
from dataclasses import dataclass


@dataclass
class ScoreFactor:
    name: str
    value: float
    z_score: float
    weight: float = 1.0
    label: str = ""


@dataclass
class CompositeScoreResult:
    score: float  # 0-100
    factors_available: int
    factors_total: int
    factors: list[dict]


def compute_health_score(factors: list[ScoreFactor], total_expected: int | None = None) -> CompositeScoreResult:
    """Compute Solana Health Score (0-100) from weighted z-score factors.

    Z-scores are mapped to a 0-100 scale:
    - z=0 maps to 50 (neutral)
    - z=+3 maps to ~95 (very bullish)
    - z=-3 maps to ~5 (very bearish)
    Uses sigmoid-like scaling: score = 50 + 50 * tanh(z / 2)
    """
    import math

    if not factors:
        return CompositeScoreResult(
            score=50.0,
            factors_available=0,
            factors_total=total_expected or 0,
            factors=[],
        )

    total_weight = sum(f.weight for f in factors)
    weighted_z = sum(f.z_score * f.weight for f in factors) / total_weight

    # Sigmoid mapping: z-score → 0-100
    raw_score = 50 + 50 * math.tanh(weighted_z / 2)
    clamped_score = max(0, min(100, raw_score))

    factor_details = []
    for f in factors:
        contribution = 50 * math.tanh(f.z_score / 2) * (f.weight / total_weight)
        factor_details.append({
            "name": f.name,
            "value": f.value,
            "z_score": round(f.z_score, 2),
            "normalized": round(math.tanh(f.z_score / 2), 2),
            "contribution": round(contribution, 2),
            "label": f.label or f.name,
        })

    return CompositeScoreResult(
        score=round(clamped_score, 1),
        factors_available=len(factors),
        factors_total=total_expected or len(factors),
        factors=factor_details,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scores.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/scores.py backend/tests/test_scores.py
git commit -m "feat: composite health score with weighted z-score sigmoid mapping"
```

---

### Task 18: Pulse Router

**Files:**
- Create: `backend/app/routers/pulse.py`
- Create: `backend/tests/test_pulse_router.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_pulse_router.py
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.cache import MemoryCache

def test_pulse_endpoint_returns_structure():
    """Test that /api/pulse returns the expected shape even with no data."""
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/pulse")
    assert resp.status_code == 200
    data = resp.json()
    assert "health_score" in data
    assert "sol_price" in data
    assert "tps" in data
    assert "priority_fees" in data
    assert "stablecoin_supply" in data
    assert "dex_volume" in data
    assert "tvl" in data
    assert "fear_greed" in data
    assert "google_trends" in data
    assert "last_updated" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pulse_router.py -v`
Expected: FAIL — no /api/pulse route

- [ ] **Step 3: Implement pulse router**

```python
# backend/app/routers/pulse.py
from datetime import datetime, timezone
from fastapi import APIRouter

from app.cache import MemoryCache
from app.analysis.scores import compute_health_score, ScoreFactor
from app.analysis.zscore import compute_zscore

router = APIRouter(prefix="/api/pulse", tags=["pulse"])

_cache: MemoryCache | None = None


def set_cache(cache: MemoryCache):
    global _cache
    _cache = cache


def _get_cached(source: str, metric: str) -> dict | None:
    if _cache is None:
        return None
    return _cache.get(f"{source}:{metric}")


@router.get("")
async def get_pulse():
    # Gather all cached metrics
    sol_price_data = _get_cached("coingecko", "sol_price")
    tps_data = _get_cached("solana_rpc", "tps")
    fees_data = _get_cached("solana_rpc", "priority_fees")
    stablecoin_data = _get_cached("solana_rpc", "stablecoin_supply")
    dex_vol_data = _get_cached("defillama", "dex_volume_24h")
    tvl_data = _get_cached("defillama", "solana_tvl")
    chains_data = _get_cached("defillama", "chains_tvl")
    fear_greed_data = _get_cached("fear_greed", "fear_greed")
    trends_data = _get_cached("google_trends", "google_trends")

    # Build health score from available factors
    factors = []
    # Note: In production, z-scores would be computed against historical DB data.
    # For MVP, we use simple heuristic mappings.
    if tps_data:
        # TPS z-score: 2000 is roughly average, higher is better
        z = (tps_data["value"] - 2000) / 500
        factors.append(ScoreFactor(name="tps", value=tps_data["value"], z_score=z, weight=1.0, label="Network TPS"))
    if fees_data:
        # Higher fees = more demand = bullish
        z = (fees_data["value"] - 5000) / 3000
        factors.append(ScoreFactor(name="priority_fees", value=fees_data["value"], z_score=z, weight=0.8, label="Priority Fees"))
    if dex_vol_data:
        # DEX volume z-score: rough baseline 500M
        z = (dex_vol_data["value"] - 500_000_000) / 200_000_000
        factors.append(ScoreFactor(name="dex_volume", value=dex_vol_data["value"], z_score=z, weight=1.5, label="DEX Volume 24h"))
    if tvl_data:
        z = (tvl_data["value"] - 4_000_000_000) / 1_000_000_000
        factors.append(ScoreFactor(name="tvl", value=tvl_data["value"], z_score=z, weight=1.0, label="Total Value Locked"))
    if stablecoin_data:
        z = (stablecoin_data["value"] - 25_000_000) / 10_000_000
        factors.append(ScoreFactor(name="stablecoin_supply", value=stablecoin_data["value"], z_score=z, weight=1.0, label="Stablecoin Supply"))
    if fear_greed_data:
        # Fear & Greed: 0-100, 50 is neutral
        z = (fear_greed_data["value"] - 50) / 25
        factors.append(ScoreFactor(name="fear_greed", value=fear_greed_data["value"], z_score=z, weight=0.5, label="Fear & Greed"))

    health_score = compute_health_score(factors, total_expected=6)

    return {
        "health_score": {
            "score": health_score.score,
            "max_score": 100,
            "factors_available": health_score.factors_available,
            "factors_total": health_score.factors_total,
            "factors": health_score.factors,
        },
        "sol_price": _format_sol_price(sol_price_data),
        "tps": _format_simple(tps_data),
        "priority_fees": _format_simple(fees_data),
        "stablecoin_supply": _format_stablecoin(stablecoin_data),
        "dex_volume": _format_simple(dex_vol_data),
        "tvl": _format_tvl(tvl_data, chains_data),
        "fear_greed": _format_fear_greed(fear_greed_data),
        "google_trends": _format_trends(trends_data),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def _format_sol_price(data: dict | None) -> dict | None:
    if not data:
        return None
    md = data.get("metadata", {})
    return {
        "value": data["value"],
        "change_24h": md.get("change_24h", 0),
        "change_7d": md.get("change_7d", 0),
        "change_30d": md.get("change_30d", 0),
    }


def _format_simple(data: dict | None) -> dict | None:
    if not data:
        return None
    return {"current": data["value"], "fetched_at": data.get("fetched_at")}


def _format_stablecoin(data: dict | None) -> dict | None:
    if not data:
        return None
    md = data.get("metadata", {})
    return {"total": data["value"], "usdc": md.get("usdc", 0), "usdt": md.get("usdt", 0)}


def _format_tvl(tvl_data: dict | None, chains_data: dict | None) -> dict | None:
    if not tvl_data:
        return None
    result = {"current": tvl_data["value"]}
    if tvl_data.get("metadata", {}).get("history"):
        result["history"] = tvl_data["metadata"]["history"]
    if chains_data and chains_data.get("metadata", {}).get("chains"):
        result["chains"] = chains_data["metadata"]["chains"]
    return result


def _format_fear_greed(data: dict | None) -> dict | None:
    if not data:
        return None
    return {"value": data["value"], "label": data.get("metadata", {}).get("label", "Unknown")}


def _format_trends(data: dict | None) -> dict | None:
    if not data:
        return None
    md = data.get("metadata", {})
    return {"solana": md.get("solana", 0), "ethereum": md.get("ethereum", 0), "bitcoin": md.get("bitcoin", 0)}
```

- [ ] **Step 4: Register pulse router in main.py**

Add to `backend/app/main.py` imports:
```python
from app.routers.pulse import router as pulse_router, set_cache as set_pulse_cache
```

Add after `set_fetchers(all_fetchers)`:
```python
set_pulse_cache(cache)
```

Add after `app.include_router(health_router)`:
```python
app.include_router(pulse_router)
```

Also register all Phase 2 fetchers in `main.py`'s lifespan:
```python
from app.fetchers.solana_rpc import SolanaRpcFetcher
from app.fetchers.coingecko import CoinGeckoFetcher
from app.fetchers.defillama import DefiLlamaFetcher
from app.fetchers.fear_greed import FearGreedFetcher
from app.fetchers.google_trends import GoogleTrendsFetcher

# Inside lifespan, after dexscreener creation:
solana_rpc = SolanaRpcFetcher(cache=cache, http_client=http_client, rpc_url=settings.solana_rpc_url)
coingecko = CoinGeckoFetcher(cache=cache, http_client=http_client, api_key=settings.coingecko_api_key)
defillama = DefiLlamaFetcher(cache=cache, http_client=http_client)
fear_greed = FearGreedFetcher(cache=cache, http_client=http_client)
google_trends = GoogleTrendsFetcher(cache=cache, http_client=http_client)

all_fetchers = [dexscreener, solana_rpc, coingecko, defillama, fear_greed, google_trends]

# Register jobs
register_fetcher_job(solana_rpc, settings.fetch_interval_rpc)
register_fetcher_job(coingecko, settings.fetch_interval_coingecko)
register_fetcher_job(defillama, settings.fetch_interval_defillama)
register_fetcher_job(fear_greed, settings.fetch_interval_fear_greed)
register_fetcher_job(google_trends, settings.fetch_interval_google_trends)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_pulse_router.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/pulse.py backend/tests/test_pulse_router.py backend/app/main.py
git commit -m "feat: pulse API endpoint with health score and all metric aggregation"
```

---

### Task 19: Frontend — Reusable Score & Metric Components

**Files:**
- Create: `frontend/src/components/scores/ScoreCard.tsx`
- Create: `frontend/src/components/scores/FactorBreakdown.tsx`
- Create: `frontend/src/components/charts/MetricCard.tsx`
- Create: `frontend/src/components/common/StatusBadge.tsx`
- Create: `frontend/src/components/common/LastUpdated.tsx`

- [ ] **Step 1: Create ScoreCard component**

```tsx
// frontend/src/components/scores/ScoreCard.tsx
import { CompositeScore } from "../../types/api";

function scoreColor(score: number): string {
  if (score >= 70) return "text-terminal-green";
  if (score >= 40) return "text-terminal-accent";
  return "text-terminal-red";
}

function scoreLabel(score: number): string {
  if (score >= 70) return "Strong";
  if (score >= 55) return "Good";
  if (score >= 40) return "Neutral";
  if (score >= 25) return "Weak";
  return "Critical";
}

interface ScoreCardProps {
  title: string;
  score: CompositeScore | null;
}

export default function ScoreCard({ title, score }: ScoreCardProps) {
  if (!score) {
    return (
      <div className="bg-terminal-card border border-terminal-border p-6">
        <h2 className="text-sm text-terminal-muted uppercase tracking-wider">{title}</h2>
        <div className="text-terminal-muted mt-2">Loading...</div>
      </div>
    );
  }

  return (
    <div className="bg-terminal-card border border-terminal-border p-6">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm text-terminal-muted uppercase tracking-wider">{title}</h2>
        <span className="text-xs text-terminal-muted">
          {score.factors_available} of {score.factors_total} factors
        </span>
      </div>
      <div className="mt-3 flex items-baseline gap-3">
        <span className={`text-4xl font-bold ${scoreColor(score.score)}`}>
          {score.score}
        </span>
        <span className="text-lg text-terminal-muted">/ {score.max_score}</span>
        <span className={`text-sm ${scoreColor(score.score)}`}>
          {scoreLabel(score.score)}
        </span>
      </div>
      {/* Progress bar */}
      <div className="mt-3 h-1.5 bg-terminal-border overflow-hidden">
        <div
          className={`h-full transition-all duration-500 ${
            score.score >= 70 ? "bg-terminal-green" : score.score >= 40 ? "bg-terminal-accent" : "bg-terminal-red"
          }`}
          style={{ width: `${score.score}%` }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create FactorBreakdown component**

```tsx
// frontend/src/components/scores/FactorBreakdown.tsx
import { useState } from "react";
import { ScoreFactor } from "../../types/api";

interface FactorBreakdownProps {
  factors: ScoreFactor[];
}

export default function FactorBreakdown({ factors }: FactorBreakdownProps) {
  const [expanded, setExpanded] = useState(false);

  if (factors.length === 0) return null;

  return (
    <div className="bg-terminal-card border border-terminal-border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-6 py-3 flex items-center justify-between text-sm text-terminal-muted hover:text-terminal-text transition-colors"
      >
        <span>Factor Breakdown</span>
        <span>{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <div className="px-6 pb-4 space-y-2">
          {factors.map((f) => (
            <div key={f.name} className="flex items-center gap-3 text-sm">
              <span className="w-40 text-terminal-muted truncate">{f.label || f.name}</span>
              <div className="flex-1 h-2 bg-terminal-border overflow-hidden">
                <div
                  className={`h-full ${
                    f.contribution > 0 ? "bg-terminal-green" : f.contribution < 0 ? "bg-terminal-red" : "bg-terminal-muted"
                  }`}
                  style={{ width: `${Math.min(100, Math.abs(f.normalized) * 100)}%` }}
                />
              </div>
              <span
                className={`w-16 text-right ${
                  f.contribution > 0 ? "text-terminal-green" : f.contribution < 0 ? "text-terminal-red" : "text-terminal-muted"
                }`}
              >
                {f.contribution > 0 ? "+" : ""}
                {f.contribution.toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create MetricCard component**

```tsx
// frontend/src/components/charts/MetricCard.tsx
interface MetricCardProps {
  label: string;
  value: string | number | null;
  subValue?: string;
  changePercent?: number;
}

export default function MetricCard({ label, value, subValue, changePercent }: MetricCardProps) {
  return (
    <div className="bg-terminal-card border border-terminal-border p-4">
      <div className="text-xs text-terminal-muted uppercase tracking-wider">{label}</div>
      <div className="mt-1 text-xl font-bold text-terminal-text">
        {value ?? "—"}
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs">
        {changePercent !== undefined && (
          <span className={changePercent >= 0 ? "text-terminal-green" : "text-terminal-red"}>
            {changePercent >= 0 ? "+" : ""}
            {changePercent.toFixed(1)}%
          </span>
        )}
        {subValue && <span className="text-terminal-muted">{subValue}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create StatusBadge and LastUpdated**

```tsx
// frontend/src/components/common/StatusBadge.tsx
interface StatusBadgeProps {
  status: "live" | "stale" | "unavailable";
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const styles = {
    live: "bg-terminal-green/20 text-terminal-green",
    stale: "bg-terminal-accent/20 text-terminal-accent",
    unavailable: "bg-terminal-red/20 text-terminal-red",
  };
  return (
    <span className={`text-xs px-2 py-0.5 ${styles[status]}`}>
      {status.toUpperCase()}
    </span>
  );
}
```

```tsx
// frontend/src/components/common/LastUpdated.tsx
interface LastUpdatedProps {
  timestamp: string | null;
}

export default function LastUpdated({ timestamp }: LastUpdatedProps) {
  if (!timestamp) return null;
  const date = new Date(timestamp);
  const timeStr = date.toLocaleTimeString();
  return (
    <span className="text-xs text-terminal-muted animate-pulse">
      Last updated: {timeStr}
    </span>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: ScoreCard, FactorBreakdown, MetricCard, StatusBadge, LastUpdated components"
```

---

### Task 20: Frontend — Pulse Page with Real Data

**Files:**
- Create: `frontend/src/api/pulse.ts`
- Modify: `frontend/src/pages/Pulse.tsx`

- [ ] **Step 1: Create pulse API client**

```typescript
// frontend/src/api/pulse.ts
import { apiFetch } from "./client";
import { PulseData } from "../types/api";

export function fetchPulse(): Promise<PulseData> {
  return apiFetch<PulseData>("/pulse");
}
```

- [ ] **Step 2: Build full Pulse page**

```tsx
// frontend/src/pages/Pulse.tsx
import PageLayout from "../components/layout/PageLayout";
import ScoreCard from "../components/scores/ScoreCard";
import FactorBreakdown from "../components/scores/FactorBreakdown";
import MetricCard from "../components/charts/MetricCard";
import LastUpdated from "../components/common/LastUpdated";
import { useApiPolling } from "../hooks/useApiPolling";
import { PulseData } from "../types/api";

function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(2);
}

export default function Pulse() {
  const { data, loading, lastUpdated } = useApiPolling<PulseData>("/pulse", 30000);

  return (
    <PageLayout title="Solana Market Pulse">
      <div className="flex justify-end mb-4">
        <LastUpdated timestamp={lastUpdated?.toISOString() ?? null} />
      </div>

      {/* Health Score */}
      <div className="mb-4">
        <ScoreCard title="Solana Health Score" score={data?.health_score ?? null} />
      </div>
      <div className="mb-6">
        <FactorBreakdown factors={data?.health_score?.factors ?? []} />
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard
          label="SOL Price"
          value={data?.sol_price ? `$${data.sol_price.value.toFixed(2)}` : null}
          changePercent={data?.sol_price?.change_24h}
          subValue="24h"
        />
        <MetricCard
          label="Network TPS"
          value={data?.tps?.current ? Math.round(data.tps.current).toLocaleString() : null}
          subValue="tx/sec"
        />
        <MetricCard
          label="Priority Fees"
          value={data?.priority_fees?.current ? Math.round(data.priority_fees.current).toLocaleString() : null}
          subValue="avg microlamports"
        />
        <MetricCard
          label="Fear & Greed"
          value={data?.fear_greed?.value ?? null}
          subValue={data?.fear_greed?.label}
        />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard
          label="DEX Volume (24h)"
          value={data?.dex_volume ? formatNumber(data.dex_volume.current) : null}
          subValue="Solana"
        />
        <MetricCard
          label="Total Value Locked"
          value={data?.tvl ? formatNumber(data.tvl.current) : null}
          subValue="Solana"
        />
        <MetricCard
          label="Stablecoin Supply"
          value={data?.stablecoin_supply ? formatNumber(data.stablecoin_supply.total) : null}
          subValue={data?.stablecoin_supply ? `USDC: ${formatNumber(data.stablecoin_supply.usdc)}` : undefined}
        />
        <MetricCard
          label="Google Trends"
          value={data?.google_trends?.solana ?? null}
          subValue={data?.google_trends ? `ETH: ${data.google_trends.ethereum} | BTC: ${data.google_trends.bitcoin}` : undefined}
        />
      </div>

      {loading && !data && (
        <div className="text-terminal-muted text-center py-8">Loading pulse data...</div>
      )}
    </PageLayout>
  );
}
```

- [ ] **Step 3: Verify end-to-end**

Run backend: `cd backend && uvicorn app.main:app --reload --port 8000`
Run frontend: `cd frontend && npm run dev`
Open `http://localhost:5173/pulse`
Expected: Dark terminal UI with health score, factor breakdown, and 8 metric cards showing live data.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/pulse.ts frontend/src/pages/Pulse.tsx
git commit -m "feat: Pulse page with health score, factor breakdown, and live metric cards"
```

---

### Task 21: TimeSeriesChart Component + TVL Chart

**Files:**
- Create: `frontend/src/components/charts/TimeSeriesChart.tsx`
- Modify: `frontend/src/pages/Pulse.tsx` (add chart)

- [ ] **Step 1: Create TimeSeriesChart**

```tsx
// frontend/src/components/charts/TimeSeriesChart.tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

interface DataPoint {
  timestamp: string | number;
  value: number;
}

interface TimeSeriesChartProps {
  data: DataPoint[];
  label: string;
  color?: string;
  height?: number;
  formatValue?: (v: number) => string;
}

export default function TimeSeriesChart({
  data,
  label,
  color = "#f0b90b",
  height = 200,
  formatValue = (v) => v.toLocaleString(),
}: TimeSeriesChartProps) {
  if (data.length === 0) {
    return (
      <div className="bg-terminal-card border border-terminal-border p-4" style={{ height }}>
        <div className="text-xs text-terminal-muted uppercase tracking-wider mb-2">{label}</div>
        <div className="text-terminal-muted text-sm">No data available</div>
      </div>
    );
  }

  const chartData = data.map((d) => ({
    time: typeof d.timestamp === "number" ? new Date(d.timestamp * 1000).toLocaleDateString() : d.timestamp,
    value: d.value,
  }));

  return (
    <div className="bg-terminal-card border border-terminal-border p-4">
      <div className="text-xs text-terminal-muted uppercase tracking-wider mb-2">{label}</div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e1e2e" />
          <XAxis dataKey="time" tick={{ fill: "#6b7280", fontSize: 10 }} tickLine={false} />
          <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} tickLine={false} tickFormatter={formatValue} />
          <Tooltip
            contentStyle={{ backgroundColor: "#12121a", border: "1px solid #1e1e2e", color: "#e0e0e0", fontSize: 12 }}
            formatter={(value: number) => [formatValue(value), label]}
          />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Add TVL chart to Pulse page**

Add to `Pulse.tsx` below the metric cards grid:

```tsx
{/* Charts */}
<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
  <TimeSeriesChart
    data={data?.tvl?.history ?? []}
    label="Solana TVL (30d)"
    color="#f0b90b"
    height={250}
    formatValue={(v) => `$${(v / 1e9).toFixed(2)}B`}
  />
</div>
```

And add the import:
```tsx
import TimeSeriesChart from "../components/charts/TimeSeriesChart";
```

- [ ] **Step 3: Verify chart renders with real data**

Refresh `http://localhost:5173/pulse`
Expected: TVL chart shows a 30-day line chart with amber glow on dark background.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/charts/TimeSeriesChart.tsx frontend/src/pages/Pulse.tsx
git commit -m "feat: TimeSeriesChart component and TVL history chart on Pulse page"
```

---

### Task 22: Final Integration Test + Push

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest -v`
Expected: All tests pass (config, database, cache, resilience, all fetchers, analysis, router)

- [ ] **Step 2: Run backend server and verify all fetchers**

Run: `cd backend && uvicorn app.main:app --port 8000`
Check logs for: all 6 fetchers running initial fetch, no errors (pytrends may warn if Google blocks).
Hit: `http://localhost:8000/api/health` — verify all sources show status.
Hit: `http://localhost:8000/api/pulse` — verify JSON response with real data.

- [ ] **Step 3: Run frontend and verify UI**

Run: `cd frontend && npm run dev`
Open `http://localhost:5173/pulse`
Verify: Health score displays, factor breakdown expands, all 8 metric cards show data, TVL chart renders.

- [ ] **Step 4: Commit and push**

```bash
git add -A
git commit -m "feat: Phase 1-2 complete — foundation + Solana Market Pulse with live data"
git push origin master
```
