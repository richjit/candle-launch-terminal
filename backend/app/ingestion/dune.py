"""
Dune Analytics ingestion — fetches on-chain Solana metrics via saved queries
and inline SQL.

Metrics:
- new_wallets: Daily count of wallets making their first-ever transaction
- priority_fees: Daily median priority fee in SOL
- pumpfun_creates: Daily count of new tokens created on pump.fun

Uses saved queries (by ID) and inline SQL (via /api/v1/sql/execute).
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import httpx
from sqlalchemy import select, func

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)

DUNE_API_BASE = "https://api.dune.com/api/v1"

# Saved query IDs on dune.com
QUERY_IDS = {
    "new_wallets": 6916611,
    "priority_fees": 6916620,
}


def _get_api_key() -> str | None:
    key = os.environ.get("DUNE_API_KEY")
    if key:
        return key
    try:
        from app.config import get_settings
        key = get_settings().dune_api_key
        return key if key else None
    except Exception:
        return None


async def _execute_and_poll(
    http_client: httpx.AsyncClient,
    api_key: str,
    query_id: int,
    timeout_seconds: int = 300,
    poll_interval: int = 10,
) -> list[dict] | None:
    """Execute a saved Dune query by ID and poll for results."""
    headers = {"X-Dune-API-Key": api_key}

    # Execute
    resp = await http_client.post(
        f"{DUNE_API_BASE}/query/{query_id}/execute",
        headers=headers,
        json={},
        timeout=30.0,
    )
    if resp.status_code != 200:
        logger.error(f"Dune execute failed for query {query_id}: {resp.status_code} {resp.text[:200]}")
        return None

    execution_id = resp.json().get("execution_id")
    if not execution_id:
        logger.error(f"No execution_id for query {query_id}")
        return None

    logger.info(f"Dune query {query_id} submitted, execution_id={execution_id}")

    # Poll for results
    elapsed = 0
    while elapsed < timeout_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        resp = await http_client.get(
            f"{DUNE_API_BASE}/execution/{execution_id}/results",
            headers=headers,
            timeout=30.0,
        )
        if resp.status_code != 200:
            logger.warning(f"Dune poll error: {resp.status_code}")
            continue

        result = resp.json()
        state = result.get("state")

        if state == "QUERY_STATE_COMPLETED":
            rows = result.get("result", {}).get("rows", [])
            logger.info(f"Dune query {query_id} completed: {len(rows)} rows")
            return rows
        elif state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
            error = result.get("error", "unknown")
            logger.error(f"Dune query {query_id} {state}: {error}")
            return None
        else:
            logger.debug(f"Dune query {query_id}: {state} ({elapsed}s elapsed)")

    logger.error(f"Dune query {query_id} timed out after {timeout_seconds}s")
    return None


PUMPFUN_CREATES_SQL = """\
SELECT DATE_TRUNC('day', block_time) as day, COUNT(*) as creates
FROM (
    SELECT MIN(block_time) as block_time, token_mint_address
    FROM tokens_solana.transfers
    WHERE block_time >= NOW() - INTERVAL '90' DAY
      AND action = 'mint'
      AND amount > 0
    GROUP BY token_mint_address
) t
GROUP BY 1
ORDER BY 1
"""

# Count daily token migrations = tokens that had their first-ever DEX trade.
# Excludes pump.fun bonding curve (pumpdotfun project) — only counts real DEX trades.
# This is the universal migration signal across all launchpads.
DEX_MIGRATIONS_SQL = """\
WITH first_trade AS (
    SELECT
        token_bought_mint_address AS token_mint,
        MIN(block_time) AS first_time
    FROM dex_solana.trades
    WHERE block_time >= NOW() - INTERVAL '90' DAY
      AND project != 'pumpdotfun'
      AND token_bought_mint_address != 'So11111111111111111111111111111111111111112'
    GROUP BY 1

    UNION ALL

    SELECT
        token_sold_mint_address AS token_mint,
        MIN(block_time) AS first_time
    FROM dex_solana.trades
    WHERE block_time >= NOW() - INTERVAL '90' DAY
      AND project != 'pumpdotfun'
      AND token_sold_mint_address != 'So11111111111111111111111111111111111111112'
    GROUP BY 1
)
SELECT
    DATE_TRUNC('day', MIN(first_time)) AS day,
    COUNT(*) AS migrations
FROM (
    SELECT token_mint, MIN(first_time) AS first_time
    FROM first_trade
    GROUP BY 1
) t
GROUP BY 1
ORDER BY 1
"""


async def _execute_sql_and_poll(
    http_client: httpx.AsyncClient,
    api_key: str,
    sql: str,
    timeout_seconds: int = 300,
    poll_interval: int = 15,
) -> list[dict] | None:
    """Execute inline SQL on Dune and poll for results."""
    headers = {"X-Dune-API-Key": api_key}

    resp = await http_client.post(
        f"{DUNE_API_BASE}/sql/execute",
        headers=headers,
        json={"sql": sql, "performance": "medium"},
        timeout=30.0,
    )
    if resp.status_code != 200:
        logger.error(f"Dune SQL execute failed: {resp.status_code} {resp.text[:200]}")
        return None

    execution_id = resp.json().get("execution_id")
    if not execution_id:
        logger.error("No execution_id from Dune SQL execute")
        return None

    logger.info(f"Dune SQL submitted, execution_id={execution_id}")

    elapsed = 0
    while elapsed < timeout_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        resp = await http_client.get(
            f"{DUNE_API_BASE}/execution/{execution_id}/results",
            headers=headers,
            timeout=30.0,
        )
        if resp.status_code != 200:
            logger.warning(f"Dune poll error: {resp.status_code}")
            continue

        result = resp.json()
        state = result.get("state")

        if state == "QUERY_STATE_COMPLETED":
            rows = result.get("result", {}).get("rows", [])
            logger.info(f"Dune SQL completed: {len(rows)} rows")
            return rows
        elif state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
            error = result.get("error", "unknown")
            logger.error(f"Dune SQL {state}: {error}")
            return None
        else:
            logger.debug(f"Dune SQL: {state} ({elapsed}s elapsed)")

    logger.error(f"Dune SQL timed out after {timeout_seconds}s")
    return None


async def _check_existing(engine, source: str) -> bool:
    async with get_session(engine) as session:
        result = await session.execute(
            select(func.count()).select_from(HistoricalData).where(HistoricalData.source == source)
        )
        return result.scalar() > 0


async def ingest_new_wallets(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch daily new wallet activation counts from Dune."""
    source = "new_wallets"
    if await _check_existing(engine, source):
        logger.info("New wallets data already ingested, skipping")
        return 0

    api_key = _get_api_key()
    if not api_key:
        logger.info("DUNE_API_KEY not set, skipping new_wallets ingestion")
        return 0

    rows = await _execute_and_poll(http_client, api_key, QUERY_IDS["new_wallets"])
    if rows is None:
        logger.error("Failed to fetch new wallets data from Dune")
        return 0

    db_rows = []
    for row in rows:
        day_str = row.get("day")
        value = row.get("new_wallets")
        if day_str and value is not None:
            dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
            db_rows.append(HistoricalData(source=source, date=dt, value=float(value)))

    async with get_session(engine) as session:
        session.add_all(db_rows)
        await session.commit()

    logger.info(f"Ingested {len(db_rows)} new_wallets data points from Dune")
    return len(db_rows)


async def ingest_priority_fees(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch daily median priority fee data from Dune."""
    source = "priority_fees"
    if await _check_existing(engine, source):
        logger.info("Priority fees data already ingested, skipping")
        return 0

    api_key = _get_api_key()
    if not api_key:
        logger.info("DUNE_API_KEY not set, skipping priority_fees ingestion")
        return 0

    rows = await _execute_and_poll(http_client, api_key, QUERY_IDS["priority_fees"])
    if rows is None:
        logger.error("Failed to fetch priority fees data from Dune")
        return 0

    db_rows = []
    for row in rows:
        day_str = row.get("day")
        median_fee = row.get("median_priority_fee_sol")
        if day_str and median_fee is not None:
            dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
            db_rows.append(HistoricalData(
                source=source,
                date=dt,
                value=float(median_fee),
                metadata_json=json.dumps({"median_sol": float(median_fee)}),
            ))

    async with get_session(engine) as session:
        session.add_all(db_rows)
        await session.commit()

    logger.info(f"Ingested {len(db_rows)} priority_fees data points from Dune")
    return len(db_rows)


async def ingest_pumpfun_creates(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch daily pump.fun token creation counts from Dune via inline SQL.

    Counts unique new tokens first traded on pump.fun each day.
    Stored in HistoricalData with source='pumpfun_creates'.
    """
    source = "pumpfun_creates"
    if await _check_existing(engine, source):
        logger.info("Pump.fun creates data already ingested, skipping")
        return 0

    api_key = _get_api_key()
    if not api_key:
        logger.info("DUNE_API_KEY not set, skipping pumpfun_creates ingestion")
        return 0

    rows = await _execute_sql_and_poll(http_client, api_key, PUMPFUN_CREATES_SQL)
    if rows is None:
        logger.error("Failed to fetch pump.fun creates data from Dune")
        return 0

    db_rows = []
    for row in rows:
        day_str = row.get("day")
        creates = row.get("creates")
        if day_str and creates is not None:
            dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
            db_rows.append(HistoricalData(source=source, date=dt, value=float(creates)))

    async with get_session(engine) as session:
        session.add_all(db_rows)
        await session.commit()

    logger.info(f"Ingested {len(db_rows)} pumpfun_creates data points from Dune")
    return len(db_rows)


async def ingest_dex_migrations(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch daily DEX migration counts from Dune via inline SQL.

    Counts tokens that had their first-ever trade on a real DEX each day.
    This is the universal migration signal across all launchpads.
    Stored in HistoricalData with source='dex_migrations'.
    """
    source = "dex_migrations"
    if await _check_existing(engine, source):
        logger.info("DEX migrations data already ingested, skipping")
        return 0

    api_key = _get_api_key()
    if not api_key:
        logger.info("DUNE_API_KEY not set, skipping dex_migrations ingestion")
        return 0

    rows = await _execute_sql_and_poll(http_client, api_key, DEX_MIGRATIONS_SQL, timeout_seconds=600)
    if rows is None:
        logger.error("Failed to fetch DEX migrations data from Dune")
        return 0

    db_rows = []
    for row in rows:
        day_str = row.get("day")
        migrations = row.get("migrations")
        if day_str and migrations is not None:
            dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
            db_rows.append(HistoricalData(source=source, date=dt, value=float(migrations)))

    async with get_session(engine) as session:
        session.add_all(db_rows)
        await session.commit()

    logger.info(f"Ingested {len(db_rows)} dex_migrations data points from Dune")
    return len(db_rows)
