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
    source = "tvl"
    if await _check_existing(engine, source):
        logger.info("TVL history already ingested, skipping")
        return 0
    resp = await http_client.get("https://api.llama.fi/v2/historicalChainTvl/Solana", timeout=30.0)
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
    source = "dex_volume"
    if await _check_existing(engine, source):
        logger.info("DEX volume history already ingested, skipping")
        return 0
    resp = await http_client.get("https://api.llama.fi/overview/dexs/solana", timeout=30.0)
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
    source = "stablecoin_supply"
    if await _check_existing(engine, source):
        logger.info("Stablecoin history already ingested, skipping")
        return 0
    resp = await http_client.get("https://stablecoins.llama.fi/stablecoincharts/Solana", timeout=30.0)
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
