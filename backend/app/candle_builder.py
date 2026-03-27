# backend/app/candle_builder.py
"""
Builds daily OHLCV candles from live MetricData sol_price records.

Runs on a schedule to aggregate intraday price ticks into daily candles
in HistoricalData, extending the chart beyond the static CSV data.
"""
import json
import logging
from datetime import date, timedelta, datetime, timezone

from sqlalchemy import select, func

from app.database import get_session, MetricData, HistoricalData

logger = logging.getLogger(__name__)


async def build_daily_candles(engine) -> int:
    """Aggregate MetricData sol_price records into daily OHLCV candles.

    Only builds candles for dates after the last existing sol_ohlcv record.
    For today (incomplete day), builds a partial candle that gets updated on next run.
    Returns the number of candles upserted.
    """
    async with get_session(engine) as session:
        # Find the last date we have a historical candle for
        last_candle = await session.execute(
            select(func.max(HistoricalData.date))
            .where(HistoricalData.source == "sol_ohlcv")
        )
        last_date = last_candle.scalar()

        if not last_date:
            logger.warning("No existing sol_ohlcv data — nothing to extend")
            return 0

        # Find all sol_price records from today onward (update today's candle + extend)
        today = date.today()
        start_from = min(last_date, today)
        price_query = (
            select(MetricData)
            .where(MetricData.source == "coingecko")
            .where(MetricData.metric_name == "sol_price")
            .where(MetricData.fetched_at >= datetime.combine(start_from, datetime.min.time(), tzinfo=timezone.utc))
            .order_by(MetricData.fetched_at)
        )
        result = await session.execute(price_query)
        price_rows = result.scalars().all()

        if not price_rows:
            return 0

        # Group by date
        daily: dict[date, list[float]] = {}
        for row in price_rows:
            d = row.fetched_at.date()
            daily.setdefault(d, []).append(row.value)

        count = 0
        for d, prices in sorted(daily.items()):
            if not prices or all(p == 0 for p in prices):
                continue

            o = prices[0]
            h = max(prices)
            l = min(prices)
            c = prices[-1]

            # Check if we already have a candle for this date (partial update)
            existing = await session.execute(
                select(HistoricalData)
                .where(HistoricalData.source == "sol_ohlcv")
                .where(HistoricalData.date == d)
            )
            row = existing.scalar_one_or_none()

            meta = json.dumps({"open": o, "high": h, "low": l, "close": c})

            if row:
                row.value = c
                row.metadata_json = meta
            else:
                session.add(HistoricalData(
                    source="sol_ohlcv",
                    date=d,
                    value=c,
                    metadata_json=meta,
                ))
            count += 1

        await session.commit()
        if count:
            logger.info(f"Built/updated {count} daily candle(s) from live price data")
        return count
