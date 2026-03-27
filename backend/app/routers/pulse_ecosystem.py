from datetime import datetime, timezone, timedelta

from fastapi import APIRouter
from sqlalchemy import select

from app.cache import MemoryCache
from app.database import get_session, MetricData

router = APIRouter(prefix="/api/pulse", tags=["pulse-ecosystem"])

_cache: MemoryCache | None = None
_engine = None


def set_cache(cache: MemoryCache):
    global _cache
    _cache = cache


def set_engine(engine):
    global _engine
    _engine = engine


def _get_cached(source: str, metric: str) -> dict | None:
    if _cache is None:
        return None
    return _cache.get(f"{source}:{metric}")


async def _get_sparkline(source: str, metric_name: str, days: int = 7) -> list[float]:
    """Get last N days of metric values from DB for sparkline."""
    if _engine is None:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_session(_engine) as session:
        result = await session.execute(
            select(MetricData.value)
            .where(
                MetricData.source == source,
                MetricData.metric_name == metric_name,
                MetricData.fetched_at >= cutoff,
            )
            .order_by(MetricData.fetched_at)
        )
        return [row.value for row in result.all()]


def _direction(sparkline: list[float]) -> str | None:
    if len(sparkline) < 2:
        return None
    return "up" if sparkline[-1] >= sparkline[0] else "down"


@router.get("/ecosystem")
async def get_ecosystem():
    metrics = []

    tps = _get_cached("solana_rpc", "tps")
    if tps:
        sparkline = await _get_sparkline("solana_rpc", "tps")
        metrics.append({
            "name": "tps",
            "label": "Network TPS",
            "current": tps["value"],
            "sparkline": sparkline,
            "direction": _direction(sparkline),
        })

    fees = _get_cached("solana_rpc", "priority_fees")
    if fees:
        sparkline = await _get_sparkline("solana_rpc", "priority_fees")
        metrics.append({
            "name": "priority_fees",
            "label": "Priority Fees",
            "current": fees["value"],
            "sparkline": sparkline,
            "direction": _direction(sparkline),
        })

    stablecoin = _get_cached("solana_rpc", "stablecoin_supply")
    if stablecoin:
        md = stablecoin.get("metadata", {})
        sparkline = await _get_sparkline("solana_rpc", "stablecoin_supply")
        metrics.append({
            "name": "stablecoin_supply",
            "label": "Stablecoin Supply",
            "current": stablecoin["value"],
            "sparkline": sparkline,
            "direction": _direction(sparkline),
            "sub_values": {"usdc": md.get("usdc", 0), "usdt": md.get("usdt", 0)},
        })

    trends = _get_cached("google_trends", "google_trends")
    if trends:
        md = trends.get("metadata", {})
        metrics.append({
            "name": "google_trends",
            "label": "Google Trends",
            "current": md.get("solana", 0),
            "sparkline": [],
            "direction": None,
            "sub_values": {"ethereum": md.get("ethereum", 0), "bitcoin": md.get("bitcoin", 0)},
        })

    return {
        "metrics": metrics,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
