import logging
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 365
CORRELATION_THRESHOLD = 0.15
FORWARD_RETURN_DAYS = 7
LAGS = [1, 3, 7, 14]

# Sources that map to scorable factors (source_name in historical_data)
FACTOR_SOURCES = ["tvl", "fear_greed", "dex_volume", "stablecoin_supply", "vol_regime", "chain_fees"]


@dataclass
class CorrelationResult:
    name: str
    label: str
    correlation: float  # Pearson r
    optimal_lag_days: int
    weight: float  # normalized |r|, sums to 1.0 across all in_score factors
    in_score: bool  # True if |r| >= CORRELATION_THRESHOLD and enough data
    mode: str = "returns"  # "returns" or "level" — how this factor is used in scoring


FACTOR_LABELS = {
    "tvl": "Total Value Locked",
    "fear_greed": "Fear & Greed Index",
    "dex_volume": "DEX Volume",
    "stablecoin_supply": "Stablecoin Supply (7d delta)",
    "vol_regime": "Volatility Regime",
    "chain_fees": "Chain Fee Revenue",
}

# Factors that need 7-day delta transformation before correlation
DELTA_FACTORS = {"stablecoin_supply"}

# Factors that are state indicators (test level-vs-forward-return, not return-vs-return)
# The engine tests BOTH modes and picks the stronger one automatically,
# but listing here lets us hint that level mode is expected to be stronger.
LEVEL_FACTORS = {"vol_regime"}


async def _load_series(engine, source: str) -> dict[date, float]:
    """Load a factor's historical data as a date->value dict.

    For factors in DELTA_FACTORS, computes 7-day change (delta) instead of raw value.
    """
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData.date, HistoricalData.value)
            .where(HistoricalData.source == source)
            .order_by(HistoricalData.date)
        )
        raw = [(row.date, row.value) for row in result.all()]

    if source not in DELTA_FACTORS:
        return {d: v for d, v in raw}

    # Compute 7-day delta: value[i] - value[i-7]
    raw_dict = {d: v for d, v in raw}
    delta_series = {}
    for d, v in raw:
        past_date = d - timedelta(days=7)
        if past_date in raw_dict:
            delta_series[d] = v - raw_dict[past_date]
    return delta_series


def _compute_forward_returns(prices: dict[date, float], days: int = 7) -> dict[date, float]:
    """Compute forward returns (pct change) for each date."""
    sorted_dates = sorted(prices.keys())
    returns = {}
    for i, d in enumerate(sorted_dates):
        target_idx = i + days
        if target_idx < len(sorted_dates):
            future_price = prices[sorted_dates[target_idx]]
            current_price = prices[d]
            if current_price > 0:
                returns[d] = (future_price - current_price) / current_price
    return returns


def _compute_factor_returns(
    factor_values: dict[date, float], days: int = 7
) -> dict[date, float]:
    """Compute forward returns (pct change) for a factor series."""
    sorted_dates = sorted(factor_values.keys())
    returns = {}
    for i, d in enumerate(sorted_dates):
        target_idx = i + days
        if target_idx < len(sorted_dates):
            future_val = factor_values[sorted_dates[target_idx]]
            current_val = factor_values[d]
            if current_val != 0:
                returns[d] = (future_val - current_val) / abs(current_val)
    return returns


def _pearson_at_lag(
    factor_series: dict[date, float],
    forward_returns: dict[date, float],
    lag: int,
) -> float | None:
    """Compute Pearson r between a factor series (lagged) and SOL forward returns."""
    pairs_x = []
    pairs_y = []
    for d, ret in forward_returns.items():
        lagged_date = d - timedelta(days=lag)
        if lagged_date in factor_series:
            pairs_x.append(factor_series[lagged_date])
            pairs_y.append(ret)

    if len(pairs_x) < 30:
        return None

    x = np.array(pairs_x)
    y = np.array(pairs_y)

    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0

    r = np.corrcoef(x, y)[0, 1]
    return float(r) if np.isfinite(r) else None


def _best_correlation(
    factor_series: dict[date, float],
    forward_returns: dict[date, float],
) -> tuple[float | None, int]:
    """Find best |r| across all lags. Returns (best_r, best_lag)."""
    best_r = None
    best_lag = LAGS[0]
    for lag in LAGS:
        r = _pearson_at_lag(factor_series, forward_returns, lag)
        if r is not None and (best_r is None or abs(r) > abs(best_r)):
            best_r = r
            best_lag = lag
    return best_r, best_lag


async def compute_correlations(engine) -> list[CorrelationResult]:
    """Compute correlation for each factor against SOL forward returns.

    Tests two modes for each factor:
    - "returns": correlation between factor % change and SOL forward returns
      (good for directional factors like TVL, Fear & Greed)
    - "level": correlation between factor level and SOL forward returns
      (good for state indicators like vol_regime where the level matters)

    Picks whichever mode gives a stronger |r| for each factor.
    """
    sol_prices = await _load_series(engine, "sol_ohlcv")
    if len(sol_prices) < MIN_DATA_POINTS:
        logger.warning(f"Only {len(sol_prices)} SOL price points, need {MIN_DATA_POINTS}")
        return []

    forward_returns = _compute_forward_returns(sol_prices, FORWARD_RETURN_DAYS)

    results = []
    for source in FACTOR_SOURCES:
        factor_data = await _load_series(engine, source)
        if len(factor_data) < MIN_DATA_POINTS:
            logger.info(f"Skipping {source}: only {len(factor_data)} data points (need {MIN_DATA_POINTS})")
            continue

        # Mode 1: return-vs-return correlation
        factor_returns = _compute_factor_returns(factor_data, FORWARD_RETURN_DAYS)
        ret_r, ret_lag = _best_correlation(factor_returns, forward_returns)

        # Mode 2: level-vs-forward-return correlation
        lvl_r, lvl_lag = _best_correlation(factor_data, forward_returns)

        # Pick the stronger mode
        ret_abs = abs(ret_r) if ret_r is not None else 0
        lvl_abs = abs(lvl_r) if lvl_r is not None else 0

        if ret_abs >= lvl_abs and ret_r is not None:
            best_r, best_lag, mode = ret_r, ret_lag, "returns"
        elif lvl_r is not None:
            best_r, best_lag, mode = lvl_r, lvl_lag, "level"
        else:
            continue

        logger.info(
            f"[{source}] returns r={ret_r:.4f} lag={ret_lag}d | "
            f"level r={lvl_r:.4f} lag={lvl_lag}d | "
            f"picked {mode} (r={best_r:.4f})"
        )

        results.append(CorrelationResult(
            name=source,
            label=FACTOR_LABELS.get(source, source),
            correlation=round(best_r, 4),
            optimal_lag_days=best_lag,
            weight=0.0,
            in_score=abs(best_r) >= CORRELATION_THRESHOLD,
            mode=mode,
        ))

    # Normalize weights for in_score factors
    scored = [r for r in results if r.in_score]
    if scored:
        total_abs_r = sum(abs(r.correlation) for r in scored)
        for r in scored:
            r.weight = round(abs(r.correlation) / total_abs_r, 4)

    return results
