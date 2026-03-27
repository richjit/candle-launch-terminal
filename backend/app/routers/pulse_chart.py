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
    today = date.today()
    cutoff = today - timedelta(days=days - 1) if days else None

    async with get_session(_engine) as session:
        # Fetch candles
        candle_query = (
            select(HistoricalData)
            .where(HistoricalData.source == "sol_ohlcv")
            .order_by(HistoricalData.date)
        )
        if cutoff:
            candle_query = candle_query.where(HistoricalData.date >= cutoff)
            candle_query = candle_query.where(HistoricalData.date <= today)

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
            score_query = score_query.where(DailyScore.date <= today)

        result = await session.execute(score_query)
        score_rows = result.scalars().all()

        scores = [
            {"time": int(calendar.timegm(row.date.timetuple())), "score": row.score}
            for row in score_rows
        ]

    return {"candles": candles, "scores": scores, "range": range}
