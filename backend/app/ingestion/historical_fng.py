import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, func

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)

URL = "https://api.alternative.me/fng/"
SOURCE = "fear_greed"


async def ingest_fear_greed_history(engine, http_client: httpx.AsyncClient) -> int:
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
        rows.append(HistoricalData(source=SOURCE, date=dt, value=value, metadata_json=None))

    async with get_session(engine) as session:
        session.add_all(rows)
        await session.commit()

    logger.info(f"Ingested {len(rows)} Fear & Greed history rows")
    return len(rows)
