import logging
from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import select

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 365
CORRELATION_THRESHOLD = 0.15
FORWARD_RETURN_DAYS = 7
LAGS = [1, 3, 7, 14]

# Sources that map to scorable factors (source_name in historical_data)
FACTOR_SOURCES = ["tvl", "fear_greed", "dex_volume", "stablecoin_supply"]


@dataclass
class CorrelationResult:
    name: str
    label: str
    correlation: float  # Pearson r
    optimal_lag_days: int
    weight: float  # normalized |r|, sums to 1.0 across all in_score factors
    in_score: bool  # True if |r| >= CORRELATION_THRESHOLD and enough data


FACTOR_LABELS = {
    "tvl": "Total Value Locked",
    "fear_greed": "Fear & Greed Index",
    "dex_volume": "DEX Volume",
    "stablecoin_supply": "Stablecoin Supply (7d delta)",
}

# Factors that need 7-day delta transformation before correlation
DELTA_FACTORS = {"stablecoin_supply"}


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
    from datetime import timedelta
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
        # Find the price `days` forward
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
    factor_returns: dict[date, float],
    forward_returns: dict[date, float],
    lag: int,
) -> float | None:
    """Compute Pearson r between factor returns (lagged) and SOL forward returns."""
    from datetime import timedelta

    pairs_x = []
    pairs_y = []
    for d, ret in forward_returns.items():
        lagged_date = d - timedelta(days=lag)
        if lagged_date in factor_returns:
            pairs_x.append(factor_returns[lagged_date])
            pairs_y.append(ret)

    if len(pairs_x) < 30:  # need minimum overlap
        return None

    x = np.array(pairs_x)
    y = np.array(pairs_y)

    # Handle constant arrays
    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0

    r = np.corrcoef(x, y)[0, 1]
    return float(r) if np.isfinite(r) else None


async def compute_correlations(engine) -> list[CorrelationResult]:
    """Compute rolling Pearson correlation for each factor against SOL forward returns.

    Returns a list of CorrelationResult with weights normalized so in_score factors sum to 1.0.
    """
    # Load SOL price data
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

        # Convert factor to returns for correlation (same direction as SOL forward returns)
        factor_returns = _compute_factor_returns(factor_data, FORWARD_RETURN_DAYS)

        # Test each lag, pick strongest |r|
        best_r = None
        best_lag = LAGS[0]
        for lag in LAGS:
            r = _pearson_at_lag(factor_returns, forward_returns, lag)
            if r is not None and (best_r is None or abs(r) > abs(best_r)):
                best_r = r
                best_lag = lag

        if best_r is None:
            continue

        results.append(CorrelationResult(
            name=source,
            label=FACTOR_LABELS.get(source, source),
            correlation=round(best_r, 4),
            optimal_lag_days=best_lag,
            weight=0.0,  # placeholder, normalized below
            in_score=abs(best_r) >= CORRELATION_THRESHOLD,
        ))

    # Normalize weights for in_score factors
    scored = [r for r in results if r.in_score]
    if scored:
        total_abs_r = sum(abs(r.correlation) for r in scored)
        for r in scored:
            r.weight = round(abs(r.correlation) / total_abs_r, 4)

    return results
