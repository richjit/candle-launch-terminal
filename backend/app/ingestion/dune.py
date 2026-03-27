"""
Dune Analytics ingestion — fetches on-chain Solana metrics via saved queries.

Metrics:
- new_wallets: Daily count of wallets making their first-ever transaction
- priority_fees: Daily median priority fee in SOL

Uses saved queries (free tier compatible) executed by query ID.
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
    return os.environ.get("DUNE_API_KEY")


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
