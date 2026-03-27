import calendar
import json
import math
from datetime import date, timedelta
from typing import Optional

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


def _recompute_score(factors_json: str, exclude: set[str]) -> float:
    """Recompute health score excluding certain factors.

    Uses the stored z-scores and weights, renormalizing weights
    after excluding factors.
    """
    factors = json.loads(factors_json)
    included = {k: v for k, v in factors.items() if k not in exclude}

    if not included:
        return 50.0  # neutral if no factors left

    # Renormalize weights
    total_weight = sum(f["weight"] for f in included.values())
    if total_weight == 0:
        return 50.0

    weighted_z_sum = 0.0
    for f in included.values():
        # Recompute contribution with renormalized weight
        renorm_weight = f["weight"] / total_weight
        # contribution was: sign(r) * weight * z_score
        # We need sign and z_score. sign = contribution / (weight * z_score) if both nonzero.
        # Simpler: contribution / weight gives sign * z_score
        if f["weight"] != 0:
            signed_z = f["contribution"] / f["weight"]
        else:
            signed_z = 0.0
        weighted_z_sum += renorm_weight * signed_z

    score = 50 + 50 * math.tanh(weighted_z_sum / 2)
    return max(0, min(100, round(score, 1)))


@router.get("/chart")
async def get_chart(
    range: str = Query("30d"),
    exclude: Optional[str] = Query(None),
):
    if range not in RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Invalid range: {range}. Valid: {', '.join(RANGE_DAYS)}")

    excluded_factors = set(exclude.split(",")) if exclude else set()

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

        if excluded_factors:
            scores = [
                {
                    "time": int(calendar.timegm(row.date.timetuple())),
                    "score": _recompute_score(row.factors_json, excluded_factors),
                }
                for row in score_rows
            ]
        else:
            scores = [
                {"time": int(calendar.timegm(row.date.timetuple())), "score": row.score}
                for row in score_rows
            ]

    return {"candles": candles, "scores": scores, "range": range}
