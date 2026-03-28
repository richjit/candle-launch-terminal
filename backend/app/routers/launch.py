"""API endpoints for the Launch Environment Monitor."""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func

from app.database import get_session, HistoricalData
from app.launch.models import LaunchDailyStats, LaunchToken

logger = logging.getLogger(__name__)

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
    async with get_session(_engine) as session:
        result = await session.execute(
            select(LaunchToken.last_updated)
            .order_by(LaunchToken.last_updated.desc())
            .limit(1)
        )
        ts = result.scalar_one_or_none()
        return ts.isoformat() if ts else datetime.now(timezone.utc).isoformat()


async def _get_historical_chart(source: str, range_param: str) -> list[dict]:
    """Read chart data from existing HistoricalData table."""
    cutoff = _get_range_cutoff(range_param)
    async with get_session(_engine) as session:
        result = await session.execute(
            select(HistoricalData)
            .where(HistoricalData.source == source)
            .where(HistoricalData.date >= cutoff)
            .order_by(HistoricalData.date)
        )
        rows = result.scalars().all()
    return [{"date": str(r.date), "value": r.value} for r in rows]


async def _get_live_launch_stats() -> dict:
    """Compute live stats from launch_tokens for cold-start fallback."""
    async with get_session(_engine) as session:
        result = await session.execute(
            select(LaunchToken).where(LaunchToken.checkpoint_complete == False)  # noqa: E712
        )
        tokens = result.scalars().all()

    if not tokens:
        return {}

    today_tokens = [t for t in tokens if t.created_at and t.created_at.date() == date.today()]
    alive = [t for t in tokens if t.is_alive]
    peaks = [t.mcap_peak_1h for t in tokens if t.mcap_peak_1h is not None]
    times = [t.time_to_peak_minutes for t in tokens if t.time_to_peak_minutes is not None]
    ratios = []
    for t in tokens:
        if t.buys_1h is not None and t.sells_1h and t.sells_1h > 0:
            ratios.append(t.buys_1h / t.sells_1h)

    # Group by launchpad for breakdown
    by_lp: dict[str, int] = defaultdict(int)
    for t in today_tokens:
        by_lp[t.launchpad] += 1

    return {
        "daily_launches": len(today_tokens),
        "daily_launches_breakdown": dict(by_lp),
        "total_tracked": len(tokens),
        "survival_rate": (len(alive) / len(tokens) * 100) if tokens else None,
        "median_peak_mcap_1h": median(peaks) if peaks else None,
        "median_time_to_peak": median(times) if times else None,
        "avg_buy_sell_ratio": (sum(ratios) / len(ratios)) if ratios else None,
    }


def _metric_response(name: str, stats: list, field: str, last_updated: str,
                     breakdown_field: str | None = None, breakdown_data: dict | None = None):
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


def _historical_metric_response(name: str, chart: list[dict], last_updated: str):
    current = chart[-1]["value"] if chart else None
    return {
        "name": name,
        "current": current,
        "trend": _compute_trend(chart),
        "last_updated": last_updated,
        "chart": chart,
    }


def _live_metric_response(name: str, value, last_updated: str, breakdown: dict | None = None):
    resp = {
        "name": name,
        "current": value,
        "trend": "flat",
        "last_updated": last_updated,
        "chart": [],
    }
    if breakdown:
        resp["breakdown"] = breakdown
    return resp


@router.get("/overview")
async def get_overview(range: str = Query("30d")):
    if range not in RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Invalid range: {range}")

    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    live = await _get_live_launch_stats()

    # Volume and Capital Flow always come from existing HistoricalData
    volume_chart = await _get_historical_chart("dex_volume", range)
    capital_chart = await _get_historical_chart("stablecoin_supply", range)

    if stats:
        # Aggregated data available — use it for launch metrics
        metrics = [
            _metric_response("Migration Rate", stats, "migration_rate", lu),
            _metric_response("Median Peak Mcap (1h)", stats, "median_peak_mcap_1h", lu),
            _metric_response("Time to Peak", stats, "median_time_to_peak", lu),
            _metric_response("Survival Rate (24h)", stats, "survival_rate_24h", lu),
            _metric_response("Buy/Sell Ratio", stats, "avg_buy_sell_ratio_1h", lu),
            _metric_response("Daily Launches", stats, "total_launches", lu),
        ]
    else:
        # Cold start — use live data from launch_tokens
        metrics = [
            _live_metric_response("Migration Rate", None, lu),  # Needs RPC data
            _live_metric_response("Median Peak Mcap (1h)", live.get("median_peak_mcap_1h"), lu),
            _live_metric_response("Time to Peak", live.get("median_time_to_peak"), lu),
            _live_metric_response("Survival Rate (24h)", live.get("survival_rate"), lu),
            _live_metric_response("Buy/Sell Ratio", live.get("avg_buy_sell_ratio"), lu),
            _live_metric_response("Daily Launches", live.get("daily_launches", 0), lu,
                                  live.get("daily_launches_breakdown")),
        ]

    # Always add volume and capital flow from historical data
    metrics.append(_historical_metric_response("Volume", volume_chart, lu))
    metrics.append(_historical_metric_response("Capital Flow", capital_chart, lu))

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
    chart = await _get_historical_chart("dex_volume", range)
    lu = await _get_last_enrichment_time()
    return _historical_metric_response("On-Chain Volume", chart, lu)


@router.get("/capital-flow")
async def get_capital_flow(range: str = Query("30d")):
    chart = await _get_historical_chart("stablecoin_supply", range)
    lu = await _get_last_enrichment_time()
    return _historical_metric_response("Capital Flow", chart, lu)
