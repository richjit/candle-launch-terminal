"""API endpoints for the Launch Environment Monitor."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.database import get_session
from app.launch.models import LaunchDailyStats

router = APIRouter(prefix="/api/launch", tags=["launch"])

_engine = None

RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def set_engine(engine):
    global _engine
    _engine = engine


def _get_range_cutoff(range_param: str) -> date:
    if range_param not in RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Invalid range: {range_param}. Valid: 7d, 30d, 90d")
    return date.today() - timedelta(days=RANGE_DAYS[range_param])


def _compute_trend(chart: list[dict]) -> str:
    """Determine trend from last 7 chart points."""
    if len(chart) < 2:
        return "flat"
    recent = [p["value"] for p in chart[-7:] if p["value"] is not None]
    if len(recent) < 2:
        return "flat"
    if recent[-1] > recent[0] * 1.02:
        return "up"
    elif recent[-1] < recent[0] * 0.98:
        return "down"
    return "flat"


async def _get_stats(range_param: str, launchpad: str = "all") -> list[LaunchDailyStats]:
    cutoff = _get_range_cutoff(range_param)
    async with get_session(_engine) as session:
        result = await session.execute(
            select(LaunchDailyStats)
            .where(LaunchDailyStats.launchpad == launchpad)
            .where(LaunchDailyStats.date >= cutoff)
            .order_by(LaunchDailyStats.date)
        )
        return result.scalars().all()


async def _get_breakdown(range_param: str) -> dict[str, list[LaunchDailyStats]]:
    cutoff = _get_range_cutoff(range_param)
    async with get_session(_engine) as session:
        result = await session.execute(
            select(LaunchDailyStats)
            .where(LaunchDailyStats.launchpad != "all")
            .where(LaunchDailyStats.date >= cutoff)
            .order_by(LaunchDailyStats.date)
        )
        rows = result.scalars().all()
    breakdown: dict[str, list[LaunchDailyStats]] = {}
    for row in rows:
        breakdown.setdefault(row.launchpad, []).append(row)
    return breakdown


async def _get_last_enrichment_time() -> str:
    """Get the most recent token update time as the real 'last_updated' indicator."""
    async with get_session(_engine) as session:
        from app.launch.models import LaunchToken
        result = await session.execute(
            select(LaunchToken.last_updated)
            .order_by(LaunchToken.last_updated.desc())
            .limit(1)
        )
        ts = result.scalar_one_or_none()
        return ts.isoformat() if ts else datetime.now(timezone.utc).isoformat()


def _metric_response(name: str, stats: list, field: str, last_updated: str, breakdown_field: str | None = None, breakdown_data: dict | None = None):
    chart = [{"date": str(s.date), "value": getattr(s, field)} for s in stats]
    current = getattr(stats[-1], field) if stats else None

    resp = {
        "name": name,
        "current": current,
        "trend": _compute_trend(chart),
        "last_updated": last_updated,
        "chart": chart,
    }

    if breakdown_data and breakdown_field:
        bd = {}
        for lp, lp_stats in breakdown_data.items():
            if lp_stats:
                bd[lp] = getattr(lp_stats[-1], breakdown_field)
        resp["breakdown"] = bd
    elif breakdown_data:
        bd = {}
        for lp, lp_stats in breakdown_data.items():
            if lp_stats:
                bd[lp] = getattr(lp_stats[-1], field)
        resp["breakdown"] = bd

    return resp


@router.get("/overview")
async def get_overview(range: str = Query("30d")):
    if range not in RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Invalid range: {range}")
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()

    metrics = [
        _metric_response("Migration Rate", stats, "migration_rate", lu),
        _metric_response("Median Peak Mcap (1h)", stats, "median_peak_mcap_1h", lu),
        _metric_response("Time to Peak", stats, "median_time_to_peak", lu),
        _metric_response("Survival Rate (24h)", stats, "survival_rate_24h", lu),
        _metric_response("Buy/Sell Ratio", stats, "avg_buy_sell_ratio_1h", lu),
        _metric_response("Daily Launches", stats, "total_launches", lu),
        _metric_response("Volume", stats, "total_volume", lu),
        _metric_response("Capital Flow", stats, "total_volume", lu),  # Placeholder
    ]

    return {"metrics": metrics, "last_updated": lu}


@router.get("/migration-rate")
async def get_migration_rate(range: str = Query("30d")):
    stats = await _get_stats(range)
    breakdown = await _get_breakdown(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Migration Rate", stats, "migration_rate", lu, "migration_rate", breakdown)


@router.get("/peak-mcap")
async def get_peak_mcap(range: str = Query("30d")):
    stats = await _get_stats(range)
    breakdown = await _get_breakdown(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Median Peak Mcap", stats, "median_peak_mcap_1h", lu, "median_peak_mcap_1h", breakdown)


@router.get("/time-to-peak")
async def get_time_to_peak(range: str = Query("30d")):
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Time to Peak", stats, "median_time_to_peak", lu)


@router.get("/survival")
async def get_survival(range: str = Query("30d")):
    stats = await _get_stats(range)
    breakdown = await _get_breakdown(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Survival Rate", stats, "survival_rate_24h", lu, "survival_rate_24h", breakdown)


@router.get("/buy-sell")
async def get_buy_sell(range: str = Query("30d")):
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Buy/Sell Ratio", stats, "avg_buy_sell_ratio_1h", lu)


@router.get("/launches")
async def get_launches(range: str = Query("30d")):
    stats = await _get_stats(range)
    breakdown = await _get_breakdown(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Daily Launches", stats, "total_launches", lu, "total_launches", breakdown)


@router.get("/volume")
async def get_volume(range: str = Query("30d")):
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("On-Chain Volume", stats, "total_volume", lu)


@router.get("/capital-flow")
async def get_capital_flow(range: str = Query("30d")):
    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    return _metric_response("Capital Flow", stats, "total_volume", lu)  # Placeholder
