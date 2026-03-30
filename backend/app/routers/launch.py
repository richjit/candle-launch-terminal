"""API endpoints for the Launch Environment Monitor."""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func

from app.database import get_session, HistoricalData
from app.launch.config import BONDING_CURVE_DEXES
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


def _graduated_token_filter():
    """Common SQLAlchemy filter conditions for legitimate graduated launchpad tokens."""
    return [
        LaunchToken.mcap_peak_1h.is_not(None),
        # Exclude bonding curve pools — only include tokens on real DEXes
        LaunchToken.dex.not_in(BONDING_CURVE_DEXES),
        # Must be from a known launchpad
        LaunchToken.launchpad.is_not(None),
    ]


def _verified_token_filter():
    """Graduated tokens that also passed on-chain verification + RugCheck."""
    return _graduated_token_filter() + [
        LaunchToken.verified_pumpfun == True,  # noqa: E712
        (LaunchToken.rugcheck_score <= 500) | (LaunchToken.rugcheck_score.is_(None)),
    ]


async def _get_performance_tiers() -> dict | None:
    """Compute peak mcap percentile tiers from verified tokens in last 24h.

    Filters:
    - Address ends in 'pump' (pump.fun vanity address)
    - On-chain bonding curve PDA verified
    - RugCheck risk score acceptable (<=500)
    - Minimum $1K liquidity for best-performer selection
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    filters = _verified_token_filter() + [LaunchToken.created_at >= cutoff]

    async with get_session(_engine) as session:
        # Graduated (bonded) tokens with peak + time data
        result = await session.execute(
            select(LaunchToken.mcap_peak_1h, LaunchToken.time_to_peak_minutes,
                   LaunchToken.address, LaunchToken.pair_address)
            .where(*filters)
            .order_by(LaunchToken.mcap_peak_1h)
        )
        rows = result.all()

        # All launches including unbonded (bonding curve tokens)
        result_all = await session.execute(
            select(LaunchToken.mcap_peak_1h)
            .where(LaunchToken.mcap_peak_1h.is_not(None))
            .where(LaunchToken.created_at >= cutoff)
            .where(LaunchToken.launchpad.is_not(None))
            .order_by(LaunchToken.mcap_peak_1h)
        )
        all_peaks = list(result_all.scalars().all())

    peaks = [r[0] for r in rows]
    best_row = rows[-1] if rows else None

    if len(peaks) < 4:
        # Fall back to unverified graduated tokens
        fallback_filters = _graduated_token_filter() + [LaunchToken.created_at >= cutoff]
        async with get_session(_engine) as session:
            result = await session.execute(
                select(LaunchToken.mcap_peak_1h, LaunchToken.time_to_peak_minutes,
                       LaunchToken.address, LaunchToken.pair_address)
                .where(*fallback_filters)
                .order_by(LaunchToken.mcap_peak_1h)
            )
            rows = result.all()

        peaks = [r[0] for r in rows]
        best_row = rows[-1] if rows else None

        if len(peaks) < 4:
            return None

    n = len(peaks)
    p90_idx = int(n * 0.9)
    p99_idx = int(n * 0.99) if n >= 100 else n - 1

    tiers: dict = {
        "bonded": peaks[n // 2],
        "top10": peaks[p90_idx],
        "top1": peaks[p99_idx],
        "best24h": peaks[-1],
        "sample_size": n,
    }

    # Time to peak broken down by performance tier
    def _median_time(token_rows):
        times = [r[1] for r in token_rows if r[1] is not None]
        return median(times) if times else None

    tiers["time_to_peak"] = {
        "bonded": _median_time(rows),
        "top10": _median_time(rows[p90_idx:]),
        "top1": _median_time(rows[p99_idx:]),
        "best24h": rows[-1][1] if rows else None,
    }

    if all_peaks:
        tiers["all_median"] = all_peaks[len(all_peaks) // 2]
        tiers["all_count"] = len(all_peaks)

    if best_row:
        tiers["best_address"] = best_row[2]
        tiers["best_pair"] = best_row[3]

    return tiers


async def _get_live_launch_stats() -> dict:
    """Compute live stats from launch_tokens for cold-start fallback."""
    async with get_session(_engine) as session:
        result = await session.execute(
            select(LaunchToken).where(LaunchToken.checkpoint_complete == False)  # noqa: E712
        )
        tokens = result.scalars().all()

    if not tokens:
        return {}

    # Rolling 24h window for graduated tokens (exclude bonding curve pools)
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    def _created_after(t, cutoff):
        ca = t.created_at
        if ca is None:
            return False
        if ca.tzinfo is None:
            ca = ca.replace(tzinfo=timezone.utc)
        return ca >= cutoff

    # All launches in 24h (including bonding curve tokens)
    recent_tokens = [t for t in tokens if _created_after(t, cutoff_24h)]
    # Graduated only (exclude bonding curve pools) for migration rate
    graduated_tokens = [t for t in recent_tokens if t.dex not in BONDING_CURVE_DEXES]
    # All metrics use the 24h window
    alive = [t for t in recent_tokens if t.is_alive]
    peaks = [t.mcap_peak_1h for t in recent_tokens if t.mcap_peak_1h is not None]
    times = [t.time_to_peak_minutes for t in recent_tokens if t.time_to_peak_minutes is not None]
    ratios = []
    for t in recent_tokens:
        if t.buys_1h is not None and t.sells_1h and t.sells_1h > 0:
            ratios.append(t.buys_1h / t.sells_1h)

    # Group by launchpad for breakdown
    by_lp: dict[str, int] = defaultdict(int)
    for t in recent_tokens:
        by_lp[t.launchpad] += 1

    # Per-launchpad graduated counts for migration breakdown
    graduated_by_lp: dict[str, int] = defaultdict(int)
    for t in graduated_tokens:
        graduated_by_lp[t.launchpad] += 1

    # Migration rate from Dune on-chain data (pump.fun decoded tables)
    # Numerator: pumpfun_graduations (pump_call_withdraw)
    # Denominator: pumpfun_creates (pump_call_create)
    migration_rate = None
    total_launches = len(recent_tokens)
    async with get_session(_engine) as session:
        # Most recent full-day creates (>5K to avoid partial days)
        result = await session.execute(
            select(HistoricalData)
            .where(HistoricalData.source == "pumpfun_creates")
            .where(HistoricalData.value >= 5000)
            .order_by(HistoricalData.date.desc())
            .limit(1)
        )
        full_day_creates = result.scalar_one_or_none()

        # Most recent graduations for the same day
        if full_day_creates:
            result2 = await session.execute(
                select(HistoricalData)
                .where(HistoricalData.source == "pumpfun_graduations")
                .where(HistoricalData.date == full_day_creates.date)
            )
            full_day_grads = result2.scalar_one_or_none()
        else:
            full_day_grads = None

        # Per-platform creates for the same day
        platform_creates = {}
        if full_day_creates:
            platform_rows = (await session.execute(
                select(HistoricalData)
                .where(HistoricalData.source.like("creates_%"))
                .where(HistoricalData.date == full_day_creates.date)
            )).scalars().all()
            for row in platform_rows:
                name = row.source.replace("creates_", "")
                platform_creates[name] = int(row.value)

        # Per-platform graduation counts
        platform_grads = {}
        if full_day_creates:
            grad_rows = (await session.execute(
                select(HistoricalData)
                .where(HistoricalData.source.like("grads_%"))
                .where(HistoricalData.date == full_day_creates.date)
            )).scalars().all()
            for row in grad_rows:
                name = row.source.replace("grads_", "")
                platform_grads[name] = int(row.value)

        total_grads = sum(platform_grads.values()) if platform_grads else (
            int(full_day_grads.value) if full_day_grads else len(graduated_tokens)
        )

        if full_day_creates and full_day_creates.value > 0:
            total_launches = int(full_day_creates.value)
            migration_rate = total_grads / full_day_creates.value * 100

    # Build per-platform migration data: creates + grads + rate
    platform_migration = {}
    for name, creates in (platform_creates or {}).items():
        grads = platform_grads.get(name, 0)
        rate = (grads / creates * 100) if creates > 0 else 0
        platform_migration[name] = {
            "creates": creates,
            "graduated": grads,
            "rate": round(rate, 2),
        }

    return {
        "daily_launches": total_launches,
        "daily_launches_breakdown": platform_creates or dict(by_lp),
        "total_tracked": len(recent_tokens),
        "survival_rate": (len(alive) / len(recent_tokens) * 100) if recent_tokens else None,
        "median_peak_mcap_1h": median(peaks) if peaks else None,
        "median_time_to_peak": median(times) if times else None,
        "avg_buy_sell_ratio": (sum(ratios) / len(ratios)) if ratios else None,
        "migration_rate": migration_rate,
        "migration_breakdown": platform_migration or dict(graduated_by_lp),
        "total_graduated": total_grads,
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


def _live_metric_response(name: str, value, last_updated: str,
                          breakdown: dict | None = None, extra: dict | None = None):
    resp = {
        "name": name,
        "current": value,
        "trend": "flat",
        "last_updated": last_updated,
        "chart": [],
    }
    if breakdown:
        resp["breakdown"] = breakdown
    if extra:
        resp.update(extra)
    return resp


@router.get("/overview")
async def get_overview(range: str = Query("30d")):
    if range not in RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Invalid range: {range}")

    stats = await _get_stats(range)
    lu = await _get_last_enrichment_time()
    live = await _get_live_launch_stats()
    tiers = await _get_performance_tiers()

    # Volume comes from existing HistoricalData
    volume_chart = await _get_historical_chart("dex_volume", range)

    if stats:
        perf = _metric_response("Launch Performance", stats, "median_peak_mcap_1h", lu)
        metrics = [
            _metric_response("Launchpad Activity", stats, "migration_rate", lu),
            _metric_response("Survival Rate (24h)", stats, "survival_rate_24h", lu),
            _metric_response("Buy/Sell Ratio", stats, "avg_buy_sell_ratio_1h", lu),
        ]
    else:
        perf = _live_metric_response("Launch Performance", live.get("median_peak_mcap_1h"), lu)
        metrics = [
            _live_metric_response("Launchpad Activity", live.get("migration_rate"), lu,
                                  breakdown=live.get("migration_breakdown"),
                                  extra={"total_graduated": live.get("total_graduated", 0),
                                         "total_launches": live.get("daily_launches", 0)}),
            _live_metric_response("Survival Rate (24h)", live.get("survival_rate"), lu),
            _live_metric_response("Buy/Sell Ratio", live.get("avg_buy_sell_ratio"), lu),
        ]

    if tiers:
        perf["tiers"] = tiers

    # Launch Performance goes first, then the rest
    metrics.insert(0, perf)

    # Add volume from historical data
    metrics.append(_historical_metric_response("Volume", volume_chart, lu))

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
    tiers = await _get_performance_tiers()
    resp = _metric_response("Launch Performance", stats, "median_peak_mcap_1h", lu, "median_peak_mcap_1h", breakdown)
    if tiers:
        resp["tiers"] = tiers
    return resp


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
