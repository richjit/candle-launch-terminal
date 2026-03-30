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


# Daily pump.fun creates (token mints from pump.fun program) + graduations
# (tokens whose first-ever DEX trade on pumpswap/raydium happened that day).
PUMPFUN_LAUNCH_STATS_SQL = """\
WITH first_dex_trade AS (
    SELECT token_bought_mint_address AS token,
           MIN(block_time) AS first_trade
    FROM dex_solana.trades
    WHERE block_time >= NOW() - INTERVAL '90' DAY
      AND project IN ('pumpswap', 'raydium')
      AND token_bought_mint_address LIKE '%pump'
    GROUP BY 1
),
creates AS (
    SELECT DATE_TRUNC('day', block_time) AS day,
           COUNT(DISTINCT token_mint_address) AS created
    FROM tokens_solana.transfers
    WHERE block_time >= NOW() - INTERVAL '90' DAY
      AND action = 'mint' AND amount > 0
      AND outer_executing_account = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
    GROUP BY 1
)
SELECT c.day, c.created,
       COUNT(f.token) AS graduated
FROM creates c
LEFT JOIN first_dex_trade f ON DATE_TRUNC('day', f.first_trade) = c.day
GROUP BY c.day, c.created
ORDER BY c.day
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


async def ingest_pumpfun_launch_stats(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch daily pump.fun launch + graduation stats from Dune.

    Uses pump.fun's decoded tables for exact counts:
    - pump_call_create = tokens created
    - pump_call_withdraw = tokens graduated (filled bonding curve)

    Stores creates in 'pumpfun_creates' and graduations in 'pumpfun_graduations'.
    """
    if await _check_existing(engine, "pumpfun_creates"):
        logger.info("Pump.fun launch stats already ingested, skipping")
        return 0

    api_key = _get_api_key()
    if not api_key:
        logger.info("DUNE_API_KEY not set, skipping pumpfun launch stats")
        return 0

    rows = await _execute_sql_and_poll(http_client, api_key, PUMPFUN_LAUNCH_STATS_SQL, timeout_seconds=600)
    if rows is None:
        logger.error("Failed to fetch pump.fun launch stats from Dune")
        return 0

    db_rows = []
    for row in rows:
        day_str = row.get("day")
        if not day_str:
            continue
        dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()

        created = row.get("created")
        graduated = row.get("graduated")

        if created is not None:
            db_rows.append(HistoricalData(source="pumpfun_creates", date=dt, value=float(created)))
        if graduated is not None:
            db_rows.append(HistoricalData(source="pumpfun_graduations", date=dt, value=float(graduated)))

    async with get_session(engine) as session:
        session.add_all(db_rows)
        await session.commit()

    logger.info(f"Ingested {len(db_rows)} pump.fun launch stat rows from Dune")
    return len(db_rows)


async def refresh_pumpfun_launch_stats(engine, http_client: httpx.AsyncClient) -> int:
    """Daily refresh: fetch latest pump.fun stats and upsert recent days.

    Only fetches last 3 days to keep it fast, and upserts (updates existing rows).
    Designed to run on a daily schedule.
    """
    api_key = _get_api_key()
    if not api_key:
        return 0

    # Shorter query: just last 3 days
    sql = """\
    WITH first_dex_trade AS (
        SELECT token_bought_mint_address AS token,
               MIN(block_time) AS first_trade
        FROM dex_solana.trades
        WHERE block_time >= NOW() - INTERVAL '7' DAY
          AND project IN ('pumpswap', 'raydium')
          AND token_bought_mint_address LIKE '%pump'
        GROUP BY 1
        HAVING MIN(block_time) >= NOW() - INTERVAL '3' DAY
    ),
    creates AS (
        SELECT DATE_TRUNC('day', block_time) AS day,
               COUNT(DISTINCT token_mint_address) AS created
        FROM tokens_solana.transfers
        WHERE block_time >= NOW() - INTERVAL '3' DAY
          AND action = 'mint' AND amount > 0
          AND outer_executing_account = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
        GROUP BY 1
    )
    SELECT c.day, c.created, COUNT(f.token) AS graduated
    FROM creates c
    LEFT JOIN first_dex_trade f ON DATE_TRUNC('day', f.first_trade) = c.day
    GROUP BY c.day, c.created
    ORDER BY c.day
    """

    rows = await _execute_sql_and_poll(http_client, api_key, sql, timeout_seconds=120)
    if rows is None:
        logger.warning("Failed to refresh pump.fun launch stats")
        return 0

    updated = 0
    async with get_session(engine) as session:
        for row in rows:
            day_str = row.get("day")
            if not day_str:
                continue
            dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()

            for source, key in [("pumpfun_creates", "created"), ("pumpfun_graduations", "graduated")]:
                value = row.get(key)
                if value is None:
                    continue

                existing = (await session.execute(
                    select(HistoricalData)
                    .where(HistoricalData.source == source)
                    .where(HistoricalData.date == dt)
                )).scalar_one_or_none()

                if existing:
                    existing.value = float(value)
                else:
                    session.add(HistoricalData(source=source, date=dt, value=float(value)))
                updated += 1

        await session.commit()

    if updated:
        logger.info(f"Refreshed {updated} pump.fun launch stat rows from Dune")
    return updated
