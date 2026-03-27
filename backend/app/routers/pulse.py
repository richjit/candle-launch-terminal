# backend/app/routers/pulse.py
from datetime import datetime, timezone
from fastapi import APIRouter

from app.cache import MemoryCache
from app.analysis.scores import compute_health_score, ScoreFactor

router = APIRouter(prefix="/api/pulse", tags=["pulse"])

_cache: MemoryCache | None = None


def set_cache(cache: MemoryCache):
    global _cache
    _cache = cache


def _get_cached(source: str, metric: str) -> dict | None:
    if _cache is None:
        return None
    return _cache.get(f"{source}:{metric}")


@router.get("")
async def get_pulse():
    # Gather all cached metrics
    sol_price_data = _get_cached("coingecko", "sol_price")
    tps_data = _get_cached("solana_rpc", "tps")
    fees_data = _get_cached("solana_rpc", "priority_fees")
    stablecoin_data = _get_cached("solana_rpc", "stablecoin_supply")
    dex_vol_data = _get_cached("defillama", "dex_volume_24h")
    tvl_data = _get_cached("defillama", "solana_tvl")
    chains_data = _get_cached("defillama", "chains_tvl")
    stablecoin_flows_data = _get_cached("defillama", "stablecoin_flows")
    fear_greed_data = _get_cached("fear_greed", "fear_greed")
    trends_data = _get_cached("google_trends", "google_trends")

    # Build health score from available factors
    factors = []
    if tps_data:
        z = (tps_data["value"] - 2000) / 500
        factors.append(ScoreFactor(name="tps", value=tps_data["value"], z_score=z, weight=1.0, label="Network TPS"))
    if fees_data:
        z = (fees_data["value"] - 5000) / 3000
        factors.append(ScoreFactor(name="priority_fees", value=fees_data["value"], z_score=z, weight=0.8, label="Priority Fees"))
    if dex_vol_data:
        z = (dex_vol_data["value"] - 500_000_000) / 200_000_000
        factors.append(ScoreFactor(name="dex_volume", value=dex_vol_data["value"], z_score=z, weight=1.5, label="DEX Volume 24h"))
    if tvl_data:
        z = (tvl_data["value"] - 4_000_000_000) / 1_000_000_000
        factors.append(ScoreFactor(name="tvl", value=tvl_data["value"], z_score=z, weight=1.0, label="Total Value Locked"))
    if stablecoin_data:
        z = (stablecoin_data["value"] - 25_000_000_000) / 10_000_000_000
        factors.append(ScoreFactor(name="stablecoin_supply", value=stablecoin_data["value"], z_score=z, weight=1.0, label="Stablecoin Supply"))
    if stablecoin_flows_data:
        z = (stablecoin_flows_data["value"] - 4_000_000_000) / 1_000_000_000
        factors.append(ScoreFactor(name="stablecoin_flows", value=stablecoin_flows_data["value"], z_score=z, weight=1.0, label="Stablecoin Capital"))
    if fear_greed_data:
        z = (fear_greed_data["value"] - 50) / 25
        factors.append(ScoreFactor(name="fear_greed", value=fear_greed_data["value"], z_score=z, weight=0.5, label="Fear & Greed"))

    health_score = compute_health_score(factors, total_expected=7)

    return {
        "health_score": {
            "score": health_score.score,
            "max_score": 100,
            "factors_available": health_score.factors_available,
            "factors_total": health_score.factors_total,
            "factors": health_score.factors,
        },
        "sol_price": _format_sol_price(sol_price_data),
        "tps": _format_simple(tps_data),
        "priority_fees": _format_simple(fees_data),
        "stablecoin_supply": _format_stablecoin(stablecoin_data),
        "dex_volume": _format_simple(dex_vol_data),
        "tvl": _format_tvl(tvl_data, chains_data),
        "stablecoin_flows": _format_stablecoin_flows(stablecoin_flows_data),
        "fear_greed": _format_fear_greed(fear_greed_data),
        "google_trends": _format_trends(trends_data),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def _format_sol_price(data: dict | None) -> dict | None:
    if not data:
        return None
    md = data.get("metadata", {})
    return {
        "value": data["value"],
        "change_24h": md.get("change_24h", 0),
        "change_7d": md.get("change_7d", 0),
        "change_30d": md.get("change_30d", 0),
    }


def _format_simple(data: dict | None) -> dict | None:
    if not data:
        return None
    return {"current": data["value"], "fetched_at": data.get("fetched_at")}


def _format_stablecoin(data: dict | None) -> dict | None:
    if not data:
        return None
    md = data.get("metadata", {})
    return {"total": data["value"], "usdc": md.get("usdc", 0), "usdt": md.get("usdt", 0)}


def _format_tvl(tvl_data: dict | None, chains_data: dict | None) -> dict | None:
    if not tvl_data:
        return None
    result = {"current": tvl_data["value"]}
    if tvl_data.get("metadata", {}).get("history"):
        result["history"] = tvl_data["metadata"]["history"]
    if chains_data and chains_data.get("metadata", {}).get("chains"):
        result["chains"] = chains_data["metadata"]["chains"]
    return result


def _format_fear_greed(data: dict | None) -> dict | None:
    if not data:
        return None
    return {"value": data["value"], "label": data.get("metadata", {}).get("label", "Unknown")}


def _format_stablecoin_flows(data: dict | None) -> dict | None:
    if not data:
        return None
    md = data.get("metadata", {})
    return {"solana": data["value"], "chains": md}


def _format_trends(data: dict | None) -> dict | None:
    if not data:
        return None
    md = data.get("metadata", {})
    return {"solana": md.get("solana", 0), "ethereum": md.get("ethereum", 0), "bitcoin": md.get("bitcoin", 0)}
