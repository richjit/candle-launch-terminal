# Narrative Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Narrative Tracker that scans DexScreener for trending Solana tokens, classifies them into narratives using Groq LLM, and shows devs what's trending and which tokens are exploding.

**Architecture:** Scheduled job every 20 min fetches trending tokens from DexScreener, filters duplicates and scams, classifies narratives via Groq, computes lifecycle stages. Frontend shows ranked narrative cards + top 10 runners.

**Tech Stack:** Python/FastAPI, SQLAlchemy, httpx, Groq API (llama-3.1-8b-instant), React/TypeScript, Tailwind CSS

---

### Task 1: Database Models

**Files:**
- Create: `backend/app/narrative/__init__.py`
- Create: `backend/app/narrative/models.py`
- Create: `backend/tests/test_narrative_models.py`

- [ ] **Step 1: Write failing test for NarrativeToken model**

```python
# backend/tests/test_narrative_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_narrative_models.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create models**

```python
# backend/app/narrative/__init__.py
# (empty)
```

```python
# backend/app/narrative/models.py
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class NarrativeToken(Base):
    __tablename__ = "narrative_tokens"

    address: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(20))
    pair_address: Mapped[str] = mapped_column(String(60))
    narrative: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    mcap: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_original: Mapped[bool] = mapped_column(Boolean, default=True)
    parent_address: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rugcheck_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Narrative(Base):
    __tablename__ = "narratives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    total_volume: Mapped[float] = mapped_column(Float, default=0)
    avg_gain_pct: Mapped[float] = mapped_column(Float, default=0)
    top_token_address: Mapped[str | None] = mapped_column(String(60), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(20), default="emerging")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_narrative_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/narrative/ backend/tests/test_narrative_models.py
git commit -m "feat(narrative): add NarrativeToken and Narrative models"
```

---

### Task 2: DexScreener Scanner

**Files:**
- Create: `backend/app/narrative/scanner.py`
- Create: `backend/tests/test_narrative_scanner.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_narrative_scanner.py
import pytest
import httpx
import respx
from app.narrative.scanner import scan_trending_tokens

MOCK_RESPONSE = [
    {
        "chainId": "solana",
        "dexId": "pumpswap",
        "pairAddress": "pair1",
        "baseToken": {"address": "token1pump", "name": "DogAI", "symbol": "DOGAI"},
        "priceUsd": "0.001",
        "marketCap": 50000,
        "volume": {"h24": 100000},
        "liquidity": {"usd": 10000},
        "priceChange": {"h24": 250.0},
        "pairCreatedAt": 1774300000000,
    },
    {
        "chainId": "solana",
        "dexId": "raydium",
        "pairAddress": "pair2",
        "baseToken": {"address": "token2abc", "name": "CatCoin", "symbol": "CAT"},
        "priceUsd": "0.05",
        "marketCap": 200000,
        "volume": {"h24": 500000},
        "liquidity": {"usd": 50000},
        "priceChange": {"h24": 180.0},
        "pairCreatedAt": 1774300000000,
    },
]


@pytest.mark.asyncio
@respx.mock
async def test_scan_trending_tokens():
    respx.get("https://api.dexscreener.com/token-boosts/top/v1").mock(
        return_value=httpx.Response(200, json=MOCK_RESPONSE)
    )
    async with httpx.AsyncClient() as client:
        tokens = await scan_trending_tokens(client)
    assert len(tokens) >= 1
    assert tokens[0]["name"] == "DogAI"
    assert tokens[0]["address"] == "token1pump"


@pytest.mark.asyncio
@respx.mock
async def test_scan_filters_non_solana():
    data = [{"chainId": "ethereum", "baseToken": {"address": "x", "name": "Y", "symbol": "Y"}}]
    respx.get("https://api.dexscreener.com/token-boosts/top/v1").mock(
        return_value=httpx.Response(200, json=data)
    )
    async with httpx.AsyncClient() as client:
        tokens = await scan_trending_tokens(client)
    assert len(tokens) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_narrative_scanner.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement scanner**

```python
# backend/app/narrative/scanner.py
"""DexScreener scanner: fetches trending Solana tokens for narrative classification."""
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"


async def scan_trending_tokens(http_client: httpx.AsyncClient) -> list[dict]:
    """Fetch trending Solana tokens from DexScreener.

    Returns list of dicts with: address, name, symbol, pair_address,
    mcap, price_change_pct, volume_24h, liquidity_usd, created_at.
    """
    try:
        resp = await http_client.get(DEXSCREENER_BOOSTS_URL, timeout=15.0)
        resp.raise_for_status()
        pairs = resp.json()
    except Exception as e:
        logger.warning(f"DexScreener trending fetch failed: {e}")
        return []

    if not isinstance(pairs, list):
        return []

    tokens = []
    seen = set()
    for pair in pairs:
        if pair.get("chainId") != "solana":
            continue

        base = pair.get("baseToken") or {}
        address = base.get("address", "")
        if not address or address in seen:
            continue
        seen.add(address)

        volume = pair.get("volume") or {}
        liquidity = pair.get("liquidity") or {}
        price_change = pair.get("priceChange") or {}
        created_ms = pair.get("pairCreatedAt")

        created_at = (
            datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            if created_ms
            else datetime.now(timezone.utc)
        )

        tokens.append({
            "address": address,
            "name": base.get("name", ""),
            "symbol": base.get("symbol", ""),
            "pair_address": pair.get("pairAddress", ""),
            "mcap": pair.get("marketCap") or 0,
            "price_change_pct": price_change.get("h24") or 0,
            "volume_24h": volume.get("h24") or 0,
            "liquidity_usd": liquidity.get("usd") or 0,
            "created_at": created_at,
        })

    logger.info(f"Scanned {len(tokens)} trending Solana tokens")
    return tokens
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_narrative_scanner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/narrative/scanner.py backend/tests/test_narrative_scanner.py
git commit -m "feat(narrative): add DexScreener trending token scanner"
```

---

### Task 3: Filters (Duplicates + Scams)

**Files:**
- Create: `backend/app/narrative/filters.py`
- Create: `backend/tests/test_narrative_filters.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_narrative_filters.py
import pytest
import httpx
import respx
from app.narrative.filters import filter_duplicates, filter_scams


def test_filter_duplicates_exact_name():
    tokens = [
        {"address": "a1", "name": "DogAI", "symbol": "DOGAI", "mcap": 100000, "created_at": "2026-03-28T10:00:00"},
        {"address": "a2", "name": "DogAI", "symbol": "DOGAI2", "mcap": 50000, "created_at": "2026-03-28T12:00:00"},
        {"address": "a3", "name": "CatCoin", "symbol": "CAT", "mcap": 80000, "created_at": "2026-03-28T11:00:00"},
    ]
    result = filter_duplicates(tokens)
    originals = [t for t in result if t["is_original"]]
    forks = [t for t in result if not t["is_original"]]
    assert len(originals) == 2  # DogAI + CatCoin
    assert len(forks) == 1  # DogAI copy
    assert forks[0]["parent_address"] == "a1"


def test_filter_duplicates_no_duplicates():
    tokens = [
        {"address": "a1", "name": "Alpha", "symbol": "A", "mcap": 100, "created_at": "2026-03-28T10:00:00"},
        {"address": "a2", "name": "Beta", "symbol": "B", "mcap": 200, "created_at": "2026-03-28T10:00:00"},
    ]
    result = filter_duplicates(tokens)
    assert all(t["is_original"] for t in result)


@pytest.mark.asyncio
@respx.mock
async def test_filter_scams_removes_dangerous():
    tokens = [
        {"address": "good_token", "name": "Good", "symbol": "G"},
        {"address": "bad_token", "name": "Scam", "symbol": "S"},
    ]
    respx.get("https://api.rugcheck.xyz/v1/tokens/good_token/report/summary").mock(
        return_value=httpx.Response(200, json={"risks": [], "score": 0, "score_normalised": 0})
    )
    respx.get("https://api.rugcheck.xyz/v1/tokens/bad_token/report/summary").mock(
        return_value=httpx.Response(200, json={
            "risks": [{"level": "danger", "score": 5000, "name": "Single holder"}],
            "score": 5000, "score_normalised": 80
        })
    )
    async with httpx.AsyncClient() as client:
        result = await filter_scams(tokens, client)
    assert len(result) == 1
    assert result[0]["address"] == "good_token"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_narrative_filters.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement filters**

```python
# backend/app/narrative/filters.py
"""Duplicate detection and scam filtering for narrative tokens."""
import logging

import httpx

logger = logging.getLogger(__name__)

RUGCHECK_SUMMARY_URL = "https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary"
MIN_LIQUIDITY = 1000  # $1K minimum
RUGCHECK_MAX_SCORE = 500


def filter_duplicates(tokens: list[dict]) -> list[dict]:
    """Detect duplicate tokens by exact name match. Oldest = original, rest = forks."""
    by_name: dict[str, list[dict]] = {}
    for t in tokens:
        name = t["name"].strip().lower()
        by_name.setdefault(name, []).append(t)

    result = []
    for name, group in by_name.items():
        group.sort(key=lambda t: t.get("created_at", ""))
        # First is original
        original = group[0]
        original["is_original"] = True
        original["parent_address"] = None
        result.append(original)
        # Rest are forks
        for fork in group[1:]:
            fork["is_original"] = False
            fork["parent_address"] = original["address"]
            result.append(fork)

    return result


async def filter_scams(
    tokens: list[dict], http_client: httpx.AsyncClient
) -> list[dict]:
    """Filter out scam tokens using RugCheck API."""
    clean = []
    for token in tokens:
        # Skip low liquidity
        if token.get("liquidity_usd", 0) < MIN_LIQUIDITY:
            continue

        try:
            resp = await http_client.get(
                RUGCHECK_SUMMARY_URL.format(mint=token["address"]), timeout=10.0
            )
            if resp.status_code != 200:
                clean.append(token)  # Can't verify, keep it
                continue

            data = resp.json()
            risks = data.get("risks", [])
            has_danger = any(r.get("level") == "danger" for r in risks)
            if has_danger:
                total_score = sum(r.get("score", 0) for r in risks)
                if total_score > RUGCHECK_MAX_SCORE:
                    logger.debug(f"Filtered scam: {token['name']} (score={total_score})")
                    continue

            token["rugcheck_score"] = sum(r.get("score", 0) for r in risks)
            clean.append(token)
        except Exception:
            clean.append(token)  # On error, keep it

    return clean
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_narrative_filters.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/narrative/filters.py backend/tests/test_narrative_filters.py
git commit -m "feat(narrative): add duplicate detection and scam filtering"
```

---

### Task 4: Groq Narrative Classifier

**Files:**
- Create: `backend/app/narrative/classifier.py`
- Create: `backend/tests/test_narrative_classifier.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_narrative_classifier.py
import pytest
import httpx
import respx
from app.narrative.classifier import classify_narratives

MOCK_GROQ_RESPONSE = {
    "choices": [{
        "message": {
            "content": '[{"token": "DogAI", "narrative": "AI"}, {"token": "CatCoin", "narrative": "Pets"}]'
        }
    }]
}


@pytest.mark.asyncio
@respx.mock
async def test_classify_narratives():
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=MOCK_GROQ_RESPONSE)
    )
    tokens = [
        {"name": "DogAI", "symbol": "DOGAI", "address": "a1"},
        {"name": "CatCoin", "symbol": "CAT", "address": "a2"},
    ]
    async with httpx.AsyncClient() as client:
        result = await classify_narratives(tokens, "fake-api-key", client)
    assert result["a1"] == "AI"
    assert result["a2"] == "Pets"


@pytest.mark.asyncio
@respx.mock
async def test_classify_handles_groq_failure():
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(500)
    )
    tokens = [{"name": "Test", "symbol": "T", "address": "a1"}]
    async with httpx.AsyncClient() as client:
        result = await classify_narratives(tokens, "fake-key", client)
    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_narrative_classifier.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement classifier**

```python
# backend/app/narrative/classifier.py
"""Groq LLM narrative classifier for trending tokens."""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You categorize Solana meme tokens into market narratives.

Return ONLY a JSON array: [{"token": "name", "narrative": "category"}]

Categories: AI, Pets, Political, Gaming, Utility, Food, Celebrity, Meme, DeFi, Other

Rules:
- Use the token name and symbol to determine the best category
- If unsure, use "Meme" as the default
- Keep category names exactly as listed above
- No explanation, just the JSON array"""


async def classify_narratives(
    tokens: list[dict],
    api_key: str,
    http_client: httpx.AsyncClient,
) -> dict[str, str]:
    """Classify tokens into narratives using Groq LLM.

    Args:
        tokens: List of dicts with 'name', 'symbol', 'address' keys.
        api_key: Groq API key.
        http_client: Shared httpx client.

    Returns:
        Dict mapping token address -> narrative category.
    """
    if not tokens or not api_key:
        return {}

    token_list = ", ".join(f"{t['name']} ({t['symbol']})" for t in tokens)

    try:
        resp = await http_client.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Categorize: {token_list}"},
                ],
                "temperature": 0,
                "max_tokens": 1024,
            },
            timeout=30.0,
        )

        if resp.status_code != 200:
            logger.warning(f"Groq API error: {resp.status_code}")
            return {}

        content = resp.json()["choices"][0]["message"]["content"]
        # Parse JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        classifications = json.loads(content)
    except Exception as e:
        logger.warning(f"Groq classification failed: {e}")
        return {}

    # Map back to addresses
    name_to_addr = {t["name"]: t["address"] for t in tokens}
    result = {}
    for item in classifications:
        name = item.get("token", "")
        narrative = item.get("narrative", "Other")
        if name in name_to_addr:
            result[name_to_addr[name]] = narrative

    return result
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_narrative_classifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/narrative/classifier.py backend/tests/test_narrative_classifier.py
git commit -m "feat(narrative): add Groq LLM narrative classifier"
```

---

### Task 5: Pipeline Orchestrator + Lifecycle

**Files:**
- Create: `backend/app/narrative/pipeline.py`
- Create: `backend/tests/test_narrative_pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_narrative_pipeline.py
import pytest
from app.narrative.pipeline import compute_lifecycle


def test_lifecycle_emerging():
    assert compute_lifecycle(token_count=3, avg_gain=50.0, prev_volume=1000, curr_volume=2000) == "emerging"


def test_lifecycle_trending():
    assert compute_lifecycle(token_count=8, avg_gain=100.0, prev_volume=5000, curr_volume=8000) == "trending"


def test_lifecycle_saturated():
    assert compute_lifecycle(token_count=20, avg_gain=10.0, prev_volume=50000, curr_volume=45000) == "saturated"


def test_lifecycle_fading():
    assert compute_lifecycle(token_count=5, avg_gain=-20.0, prev_volume=50000, curr_volume=10000) == "fading"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_narrative_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: Implement pipeline**

```python
# backend/app/narrative/pipeline.py
"""Narrative pipeline: orchestrates scan → filter → classify → aggregate → lifecycle."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select, delete

from app.database import get_session
from app.narrative.models import NarrativeToken, Narrative
from app.narrative.scanner import scan_trending_tokens
from app.narrative.filters import filter_duplicates, filter_scams
from app.narrative.classifier import classify_narratives

logger = logging.getLogger(__name__)


def compute_lifecycle(
    token_count: int,
    avg_gain: float,
    prev_volume: float,
    curr_volume: float,
) -> str:
    """Determine narrative lifecycle stage."""
    volume_growing = curr_volume > prev_volume * 0.8

    if token_count < 5 and volume_growing:
        return "emerging"
    if token_count >= 5 and avg_gain > 30 and volume_growing:
        return "trending"
    if token_count >= 5 and (avg_gain <= 30 or not volume_growing):
        return "saturated"
    return "fading"


async def run_narrative_pipeline(engine, http_client, groq_api_key: str) -> int:
    """Full pipeline: scan → filter → classify → store → aggregate.

    Returns number of tokens processed.
    """
    now = datetime.now(timezone.utc)

    # 1. Scan
    raw_tokens = await scan_trending_tokens(http_client)
    if not raw_tokens:
        return 0

    # 2. Filter duplicates
    tokens = filter_duplicates(raw_tokens)

    # 3. Filter scams
    tokens = await filter_scams(tokens, http_client)
    if not tokens:
        return 0

    # 4. Classify with Groq
    classifications = await classify_narratives(tokens, groq_api_key, http_client)

    # 5. Store tokens
    async with get_session(engine) as session:
        for t in tokens:
            narrative = classifications.get(t["address"], "Other")

            existing = (await session.execute(
                select(NarrativeToken).where(NarrativeToken.address == t["address"])
            )).scalar_one_or_none()

            if existing:
                existing.mcap = t.get("mcap")
                existing.price_change_pct = t.get("price_change_pct")
                existing.volume_24h = t.get("volume_24h")
                existing.liquidity_usd = t.get("liquidity_usd")
                existing.narrative = narrative
                existing.is_original = t.get("is_original", True)
                existing.parent_address = t.get("parent_address")
                existing.rugcheck_score = t.get("rugcheck_score")
                existing.last_seen = now
            else:
                created_at = t.get("created_at", now)
                session.add(NarrativeToken(
                    address=t["address"],
                    name=t["name"],
                    symbol=t["symbol"],
                    pair_address=t.get("pair_address", ""),
                    narrative=narrative,
                    mcap=t.get("mcap"),
                    price_change_pct=t.get("price_change_pct"),
                    volume_24h=t.get("volume_24h"),
                    liquidity_usd=t.get("liquidity_usd"),
                    is_original=t.get("is_original", True),
                    parent_address=t.get("parent_address"),
                    rugcheck_score=t.get("rugcheck_score"),
                    created_at=created_at,
                    first_seen=now,
                    last_seen=now,
                ))

        await session.commit()

    # 6. Aggregate narratives
    await _aggregate_narratives(engine, now)

    logger.info(f"Narrative pipeline processed {len(tokens)} tokens")
    return len(tokens)


async def _aggregate_narratives(engine, now: datetime):
    """Recompute narrative aggregates from current token data."""
    async with get_session(engine) as session:
        all_tokens = (await session.execute(select(NarrativeToken))).scalars().all()

        # Group by narrative
        by_narrative: dict[str, list[NarrativeToken]] = {}
        for t in all_tokens:
            if t.narrative:
                by_narrative.setdefault(t.narrative, []).append(t)

        for name, tokens in by_narrative.items():
            gains = [t.price_change_pct for t in tokens if t.price_change_pct is not None]
            volumes = [t.volume_24h for t in tokens if t.volume_24h is not None]
            top = max(tokens, key=lambda t: t.price_change_pct or 0)

            avg_gain = sum(gains) / len(gains) if gains else 0
            total_vol = sum(volumes)

            # Get previous volume for lifecycle
            existing = (await session.execute(
                select(Narrative).where(Narrative.name == name)
            )).scalar_one_or_none()

            prev_vol = existing.total_volume if existing else 0
            lifecycle = compute_lifecycle(len(tokens), avg_gain, prev_vol, total_vol)

            if existing:
                existing.token_count = len(tokens)
                existing.total_volume = total_vol
                existing.avg_gain_pct = avg_gain
                existing.top_token_address = top.address
                existing.lifecycle = lifecycle
                existing.last_updated = now
            else:
                session.add(Narrative(
                    name=name,
                    token_count=len(tokens),
                    total_volume=total_vol,
                    avg_gain_pct=avg_gain,
                    top_token_address=top.address,
                    lifecycle=lifecycle,
                    last_updated=now,
                ))

        await session.commit()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_narrative_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/narrative/pipeline.py backend/tests/test_narrative_pipeline.py
git commit -m "feat(narrative): add pipeline orchestrator with lifecycle computation"
```

---

### Task 6: API Router

**Files:**
- Create: `backend/app/routers/narrative.py`
- Create: `backend/tests/test_narrative_api.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_narrative_api.py
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.database import init_db, get_session
from app.narrative.models import NarrativeToken, Narrative


@pytest_asyncio.fixture
async def app_with_data():
    engine = await init_db("sqlite+aiosqlite:///:memory:")

    from app.routers.narrative import router, set_engine
    set_engine(engine)

    app = FastAPI()
    app.include_router(router)

    async with get_session(engine) as session:
        session.add(Narrative(
            name="AI", token_count=10, total_volume=500000,
            avg_gain_pct=150.0, top_token_address="ai_token_1",
            lifecycle="trending", last_updated=datetime.now(timezone.utc),
        ))
        session.add(Narrative(
            name="Pets", token_count=5, total_volume=200000,
            avg_gain_pct=80.0, top_token_address="pet_token_1",
            lifecycle="emerging", last_updated=datetime.now(timezone.utc),
        ))
        session.add(NarrativeToken(
            address="ai_token_1", name="SmartAI", symbol="SAI",
            pair_address="pair1", narrative="AI", mcap=100000,
            price_change_pct=300.0, volume_24h=200000, liquidity_usd=50000,
            is_original=True, created_at=datetime.now(timezone.utc),
            first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc),
        ))
        session.add(NarrativeToken(
            address="pet_token_1", name="DogCoin", symbol="DOG",
            pair_address="pair2", narrative="Pets", mcap=50000,
            price_change_pct=120.0, volume_24h=80000, liquidity_usd=20000,
            is_original=True, created_at=datetime.now(timezone.utc),
            first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc),
        ))
        await session.commit()

    yield app
    await engine.dispose()


@pytest.mark.asyncio
async def test_overview(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/narrative/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "narratives" in data
    assert "top_runners" in data
    assert len(data["narratives"]) == 2
    # Sorted by momentum (avg_gain * volume)
    assert data["narratives"][0]["name"] == "AI"


@pytest.mark.asyncio
async def test_narrative_detail(app_with_data):
    transport = ASGITransport(app=app_with_data)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/narrative/AI")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "AI"
    assert len(data["tokens"]) == 1
    assert data["tokens"][0]["symbol"] == "SAI"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_narrative_api.py -v`
Expected: FAIL

- [ ] **Step 3: Implement router**

```python
# backend/app/routers/narrative.py
"""API endpoints for the Narrative Tracker."""
import logging
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.database import get_session
from app.narrative.models import NarrativeToken, Narrative

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/narrative", tags=["narrative"])

_engine = None


def set_engine(engine):
    global _engine
    _engine = engine


@router.get("/overview")
async def get_overview():
    """All narratives ranked by momentum + top 10 runners."""
    async with get_session(_engine) as session:
        narratives = (await session.execute(
            select(Narrative).order_by(
                (Narrative.avg_gain_pct * Narrative.total_volume).desc()
            )
        )).scalars().all()

        # Top 10 runners by % gain
        runners = (await session.execute(
            select(NarrativeToken)
            .where(NarrativeToken.price_change_pct.is_not(None))
            .order_by(NarrativeToken.price_change_pct.desc())
            .limit(10)
        )).scalars().all()

    return {
        "narratives": [
            {
                "name": n.name,
                "token_count": n.token_count,
                "total_volume": n.total_volume,
                "avg_gain_pct": n.avg_gain_pct,
                "lifecycle": n.lifecycle,
                "top_token_address": n.top_token_address,
                "last_updated": n.last_updated.isoformat() if n.last_updated else None,
            }
            for n in narratives
        ],
        "top_runners": [
            {
                "address": t.address,
                "name": t.name,
                "symbol": t.symbol,
                "narrative": t.narrative,
                "mcap": t.mcap,
                "price_change_pct": t.price_change_pct,
                "volume_24h": t.volume_24h,
                "liquidity_usd": t.liquidity_usd,
                "is_original": t.is_original,
                "parent_address": t.parent_address,
                "pair_address": t.pair_address,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in runners
        ],
    }


@router.get("/{name}")
async def get_narrative_detail(name: str):
    """Detail view for one narrative with all its tokens."""
    async with get_session(_engine) as session:
        narrative = (await session.execute(
            select(Narrative).where(Narrative.name == name)
        )).scalar_one_or_none()

        if not narrative:
            raise HTTPException(status_code=404, detail=f"Narrative '{name}' not found")

        tokens = (await session.execute(
            select(NarrativeToken)
            .where(NarrativeToken.narrative == name)
            .order_by(NarrativeToken.price_change_pct.desc())
        )).scalars().all()

    return {
        "name": narrative.name,
        "token_count": narrative.token_count,
        "total_volume": narrative.total_volume,
        "avg_gain_pct": narrative.avg_gain_pct,
        "lifecycle": narrative.lifecycle,
        "tokens": [
            {
                "address": t.address,
                "name": t.name,
                "symbol": t.symbol,
                "mcap": t.mcap,
                "price_change_pct": t.price_change_pct,
                "volume_24h": t.volume_24h,
                "liquidity_usd": t.liquidity_usd,
                "is_original": t.is_original,
                "parent_address": t.parent_address,
                "pair_address": t.pair_address,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tokens
        ],
    }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_narrative_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/narrative.py backend/tests/test_narrative_api.py
git commit -m "feat(narrative): add API router with overview and detail endpoints"
```

---

### Task 7: Wire Into Main App

**Files:**
- Modify: `backend/app/config.py` — add `fetch_interval_narrative`
- Modify: `backend/app/main.py` — import router + register scheduled job

- [ ] **Step 1: Add config**

Add to `backend/app/config.py` after the launch monitor intervals:

```python
    # Narrative tracker intervals (seconds)
    fetch_interval_narrative: int = 1200  # 20 minutes
```

- [ ] **Step 2: Wire router and job in main.py**

Add imports:

```python
from app.routers.narrative import router as narrative_router, set_engine as set_narrative_engine
from app.narrative.pipeline import run_narrative_pipeline
```

Add after `set_launch_engine(db_engine)`:

```python
    set_narrative_engine(db_engine)
```

Add after launch router include:

```python
app.include_router(narrative_router)
```

Add scheduled job after the launch monitor jobs block:

```python
    # Narrative tracker job
    scheduler.add_job(
        run_narrative_pipeline,
        args=[db_engine, http_client, settings.groq_api_key],
        trigger=IntervalTrigger(seconds=settings.fetch_interval_narrative),
        id="narrative_pipeline",
        replace_existing=True,
        max_instances=1,
    )
```

- [ ] **Step 3: Run all tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/app/main.py
git commit -m "feat(narrative): wire pipeline into scheduler and register API router"
```

---

### Task 8: Frontend Types and API

**Files:**
- Create: `frontend/src/types/narrative.ts`
- Create: `frontend/src/api/narrative.ts`

- [ ] **Step 1: Create types**

```typescript
// frontend/src/types/narrative.ts
export interface NarrativeData {
  name: string;
  token_count: number;
  total_volume: number;
  avg_gain_pct: number;
  lifecycle: "emerging" | "trending" | "saturated" | "fading";
  top_token_address: string | null;
  last_updated: string | null;
}

export interface NarrativeTokenData {
  address: string;
  name: string;
  symbol: string;
  narrative: string | null;
  mcap: number | null;
  price_change_pct: number | null;
  volume_24h: number | null;
  liquidity_usd: number | null;
  is_original: boolean;
  parent_address: string | null;
  pair_address: string;
  created_at: string | null;
}

export interface NarrativeOverview {
  narratives: NarrativeData[];
  top_runners: NarrativeTokenData[];
}

export interface NarrativeDetail {
  name: string;
  token_count: number;
  total_volume: number;
  avg_gain_pct: number;
  lifecycle: string;
  tokens: NarrativeTokenData[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/narrative.ts
git commit -m "feat(narrative): add frontend TypeScript types"
```

---

### Task 9: Narrative Dashboard Page

**Files:**
- Create: `frontend/src/pages/NarrativeDashboard.tsx`
- Modify: `frontend/src/App.tsx` — add route
- Modify: `frontend/src/components/layout/Sidebar.tsx` — add nav link

- [ ] **Step 1: Create the dashboard page**

```typescript
// frontend/src/pages/NarrativeDashboard.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import { useApiPolling } from "../hooks/useApiPolling";
import type { NarrativeOverview, NarrativeData, NarrativeTokenData } from "../types/narrative";

function formatVolume(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function formatPct(v: number | null): string {
  if (v == null) return "--";
  return `${v > 0 ? "+" : ""}${v.toFixed(0)}%`;
}

function formatAge(created: string | null): string {
  if (!created) return "--";
  const diff = Date.now() - new Date(created).getTime();
  const h = Math.floor(diff / 3600000);
  if (h >= 24) return `${Math.floor(h / 24)}d ago`;
  if (h > 0) return `${h}h ago`;
  return `${Math.floor(diff / 60000)}m ago`;
}

const LIFECYCLE_COLORS: Record<string, string> = {
  emerging: "text-blue-400 bg-blue-400/10 border-blue-400/20",
  trending: "text-terminal-green bg-terminal-green/10 border-terminal-green/20",
  saturated: "text-terminal-accent bg-terminal-accent/10 border-terminal-accent/20",
  fading: "text-terminal-red bg-terminal-red/10 border-terminal-red/20",
};

function NarrativeCard({ narrative, onClick }: { narrative: NarrativeData; onClick: () => void }) {
  const lc = LIFECYCLE_COLORS[narrative.lifecycle] || LIFECYCLE_COLORS.fading;
  return (
    <button
      onClick={onClick}
      className="bg-terminal-card border border-terminal-border rounded-lg p-4 text-left hover:border-terminal-accent/40 transition-all w-full"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-terminal-text">{narrative.name}</span>
        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${lc} capitalize`}>
          {narrative.lifecycle}
        </span>
      </div>
      <div className="flex items-center gap-4 text-xs text-terminal-muted">
        <span>{narrative.token_count} tokens</span>
        <span>{formatVolume(narrative.total_volume)} vol</span>
        <span className={narrative.avg_gain_pct > 0 ? "text-terminal-green" : "text-terminal-red"}>
          {formatPct(narrative.avg_gain_pct)} avg
        </span>
      </div>
    </button>
  );
}

function RunnerRow({ token }: { token: NarrativeTokenData }) {
  return (
    <div className="flex items-center gap-3 py-2 border-b border-terminal-border/20 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-terminal-text truncate">{token.name}</span>
          <span className="text-[10px] text-terminal-muted">{token.symbol}</span>
          {!token.is_original && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-terminal-accent/10 text-terminal-accent border border-terminal-accent/20">
              fork
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[11px] text-terminal-muted mt-0.5">
          {token.narrative && (
            <span className="text-terminal-accent">{token.narrative}</span>
          )}
          <span>{formatAge(token.created_at)}</span>
        </div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className={`text-sm font-bold tabular-nums ${
          (token.price_change_pct ?? 0) > 0 ? "text-terminal-green" : "text-terminal-red"
        }`}>
          {formatPct(token.price_change_pct)}
        </div>
        <div className="text-[11px] text-terminal-muted tabular-nums">
          {token.mcap ? formatVolume(token.mcap) : "--"}
        </div>
      </div>
      <a
        href={`https://dexscreener.com/solana/${token.address}`}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="text-[10px] text-terminal-accent/60 hover:text-terminal-accent flex-shrink-0"
      >
        DS
      </a>
    </div>
  );
}

export default function NarrativeDashboard() {
  const navigate = useNavigate();
  const { data, loading, error } = useApiPolling<NarrativeOverview>(
    "/narrative/overview",
    60000,
  );

  return (
    <PageLayout title="Narrative Tracker">
      <p className="text-sm text-terminal-muted mb-6">
        On-chain trending narratives and top runners — what to launch next
      </p>

      {loading && !data && (
        <div className="text-terminal-muted text-center py-16">Scanning trends...</div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Narratives */}
          <div className="lg:col-span-2">
            <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">
              Trending Narratives
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {data.narratives.map((n) => (
                <NarrativeCard
                  key={n.name}
                  narrative={n}
                  onClick={() => navigate(`/narrative/${encodeURIComponent(n.name)}`)}
                />
              ))}
            </div>
            {data.narratives.length === 0 && (
              <div className="text-terminal-muted text-center py-8 text-sm">
                No narratives detected yet — data populates every 20 minutes
              </div>
            )}
          </div>

          {/* Top Runners */}
          <div>
            <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">
              Top Runners (24h)
            </div>
            <div className="bg-terminal-card border border-terminal-border rounded-lg p-4">
              {data.top_runners.map((t) => (
                <RunnerRow key={t.address} token={t} />
              ))}
              {data.top_runners.length === 0 && (
                <div className="text-terminal-muted text-center py-6 text-sm">
                  No runners yet
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  );
}
```

- [ ] **Step 2: Add route to App.tsx**

Add import:

```typescript
import NarrativeDashboard from "./pages/NarrativeDashboard";
```

Add routes after the launch routes:

```tsx
<Route path="/narrative" element={<NarrativeDashboard />} />
<Route path="/narrative/:name" element={<NarrativeDetail />} />
```

Note: `NarrativeDetail` will be created in the next task.

- [ ] **Step 3: Add nav link to Sidebar**

Add a "Narratives" link to the sidebar component, following the existing pattern for "Sol Outlook" and "Launch Monitor". Link to `/narrative`.

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean (no errors)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/NarrativeDashboard.tsx frontend/src/App.tsx frontend/src/components/layout/Sidebar.tsx
git commit -m "feat(narrative): add Narrative Dashboard page with narrative cards and top runners"
```

---

### Task 10: Narrative Detail Page

**Files:**
- Create: `frontend/src/pages/NarrativeDetail.tsx`
- Modify: `frontend/src/App.tsx` — add import

- [ ] **Step 1: Create detail page**

```typescript
// frontend/src/pages/NarrativeDetail.tsx
import { useParams, useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import { useApiPolling } from "../hooks/useApiPolling";
import type { NarrativeDetail as NarrativeDetailData } from "../types/narrative";

function formatVolume(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function formatPct(v: number | null): string {
  if (v == null) return "--";
  return `${v > 0 ? "+" : ""}${v.toFixed(0)}%`;
}

export default function NarrativeDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const { data, loading, error } = useApiPolling<NarrativeDetailData>(
    `/narrative/${encodeURIComponent(name || "")}`,
    60000,
  );

  return (
    <PageLayout title={name || "Narrative"}>
      <button
        onClick={() => navigate("/narrative")}
        className="text-sm text-terminal-muted hover:text-terminal-text transition-colors mb-6"
      >
        ← Back to narratives
      </button>

      {loading && !data && <div className="text-terminal-muted text-center py-16">Loading...</div>}
      {error && <div className="text-terminal-red text-center py-4 text-sm">{error}</div>}

      {data && (
        <>
          <div className="bg-terminal-card border border-terminal-border rounded-lg p-5 mb-6">
            <div className="grid grid-cols-4 gap-6">
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Lifecycle</div>
                <div className="text-lg font-bold text-terminal-text capitalize">{data.lifecycle}</div>
              </div>
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Tokens</div>
                <div className="text-lg font-bold text-terminal-text">{data.token_count}</div>
              </div>
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Volume</div>
                <div className="text-lg font-bold text-terminal-text">{formatVolume(data.total_volume)}</div>
              </div>
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Avg Gain</div>
                <div className={`text-lg font-bold ${data.avg_gain_pct > 0 ? "text-terminal-green" : "text-terminal-red"}`}>
                  {formatPct(data.avg_gain_pct)}
                </div>
              </div>
            </div>
          </div>

          <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">
            Tokens in this narrative
          </div>
          <div className="bg-terminal-card border border-terminal-border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="text-[11px] text-terminal-muted/50 uppercase tracking-wider border-b border-terminal-border/30">
                  <th className="text-left p-3 font-medium">Token</th>
                  <th className="text-right p-3 font-medium">Mcap</th>
                  <th className="text-right p-3 font-medium">Change</th>
                  <th className="text-right p-3 font-medium">Volume</th>
                  <th className="text-right p-3 font-medium">Type</th>
                  <th className="text-right p-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {data.tokens.map((t) => (
                  <tr key={t.address} className="border-b border-terminal-border/10 hover:bg-terminal-border/5">
                    <td className="p-3">
                      <div className="text-sm font-medium text-terminal-text">{t.name}</div>
                      <div className="text-[11px] text-terminal-muted">{t.symbol}</div>
                    </td>
                    <td className="p-3 text-right text-sm tabular-nums text-terminal-text">
                      {t.mcap ? formatVolume(t.mcap) : "--"}
                    </td>
                    <td className={`p-3 text-right text-sm font-bold tabular-nums ${
                      (t.price_change_pct ?? 0) > 0 ? "text-terminal-green" : "text-terminal-red"
                    }`}>
                      {formatPct(t.price_change_pct)}
                    </td>
                    <td className="p-3 text-right text-sm tabular-nums text-terminal-muted">
                      {t.volume_24h ? formatVolume(t.volume_24h) : "--"}
                    </td>
                    <td className="p-3 text-right text-xs">
                      {t.is_original ? (
                        <span className="text-terminal-green">original</span>
                      ) : (
                        <span className="text-terminal-accent">fork</span>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      <a
                        href={`https://dexscreener.com/solana/${t.address}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-terminal-accent/60 hover:text-terminal-accent underline"
                      >
                        DexScreener
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </PageLayout>
  );
}
```

- [ ] **Step 2: Add import and route in App.tsx**

Add import:

```typescript
import NarrativeDetail from "./pages/NarrativeDetail";
```

The route was already added in Task 9.

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/NarrativeDetail.tsx frontend/src/App.tsx
git commit -m "feat(narrative): add Narrative Detail page with token table"
```

---

### Task 11: Integration Test

**Files:** No new files — end-to-end verification

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 2: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean

- [ ] **Step 3: Start backend and test endpoints**

```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Test: `curl http://localhost:8000/api/narrative/overview`
Expected: `{"narratives": [], "top_runners": []}` (empty until first scan runs)

- [ ] **Step 4: Verify frontend renders**

Open `http://localhost:5173/narrative`
Expected: "Scanning trends..." or empty narrative cards

- [ ] **Step 5: Push**

```bash
git push origin feature/narrative-tracker
```
