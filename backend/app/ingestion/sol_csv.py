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
        header = next(reader)
        # Detect if Volume column exists (Binance export has it at index 5)
        has_volume = len(header) > 5 and header[5].strip().lower() == "volume"
        for row in reader:
            if len(row) < 5:
                continue
            timestamp = int(row[0])
            open_price = float(row[1])
            high = float(row[2])
            low = float(row[3])
            close = float(row[4])
            volume = float(row[5]) if has_volume and len(row) > 5 and row[5].strip() else None
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
            meta = {
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
            }
            if volume is not None:
                meta["volume"] = volume
            rows_to_insert.append(HistoricalData(
                source=SOURCE,
                date=dt,
                value=close,
                metadata_json=json.dumps(meta),
            ))

    async with get_session(engine) as session:
        session.add_all(rows_to_insert)
        await session.commit()

    logger.info(f"Ingested {len(rows_to_insert)} SOL OHLCV rows")
    return len(rows_to_insert)
