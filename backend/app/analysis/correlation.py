"""
Correlation engine — evaluates factor predictive power against SOL forward returns.

Uses Spearman rank correlation (robust to outliers and non-linear monotonic relationships)
instead of Pearson. Tests multiple modes per factor:
- "returns": % change in factor vs SOL forward returns
- "level": raw factor value vs SOL forward returns
- "log_returns": log-transformed returns (compresses outlier-heavy factors like fees)

Also generates interaction factors (pairwise products of standardized base factors)
when they show significant predictive power.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from scipy.stats import spearmanr, rankdata
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
    correlation: float  # Spearman rho
    optimal_lag_days: int
    weight: float  # normalized |rho|, sums to 1.0 across all in_score factors
    in_score: bool  # True if |rho| >= CORRELATION_THRESHOLD and enough data
    mode: str = "returns"  # "returns", "level", or "log_returns"
    # For interaction factors: the two base factors that compose it
    components: list[str] = field(default_factory=list)


FACTOR_LABELS = {
    "tvl": "Total Value Locked",
    "fear_greed": "Fear & Greed Index",
    "dex_volume": "DEX Volume",
    "stablecoin_supply": "Stablecoin Supply",
    "vol_regime": "Volatility Regime",
    "chain_fees": "Chain Fee Revenue",
}

# Factors where 7-day delta is used as an additional mode
DELTA_FACTORS = {"stablecoin_supply"}

# Interaction pairs to test (discovered via advanced analysis)
# Only test pairs that showed p<0.01 in the research
INTERACTION_PAIRS = [
    ("fear_greed", "chain_fees"),
    ("fear_greed", "stablecoin_supply"),
    ("fear_greed", "dex_volume"),
]


async def _load_raw_series(engine, source: str) -> dict[date, float]:
    """Load a factor's raw historical data as a date->value dict."""
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData.date, HistoricalData.value)
            .where(HistoricalData.source == source)
            .order_by(HistoricalData.date)
        )
        return {row.date: row.value for row in result.all()}


async def _load_series(engine, source: str) -> dict[date, float]:
    """Load a factor's historical data, applying delta transform if needed.

    Public API used by score_backfill.
    """
    raw = await _load_raw_series(engine, source)
    if source not in DELTA_FACTORS:
        return raw

    # Compute 7-day delta
    delta_series = {}
    for d, v in raw.items():
        past_date = d - timedelta(days=7)
        if past_date in raw:
            delta_series[d] = v - raw[past_date]
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
    """Compute pct change for a factor series."""
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


def _compute_log_returns(
    factor_values: dict[date, float], days: int = 7
) -> dict[date, float]:
    """Compute log-transformed pct change. Compresses outliers in heavy-tailed factors."""
    sorted_dates = sorted(factor_values.keys())
    returns = {}
    for i, d in enumerate(sorted_dates):
        target_idx = i + days
        if target_idx < len(sorted_dates):
            future_val = factor_values[sorted_dates[target_idx]]
            current_val = factor_values[d]
            if current_val > 0 and future_val > 0:
                returns[d] = np.log(future_val / current_val)
    return returns


def _compute_delta(series: dict[date, float], days: int = 7) -> dict[date, float]:
    """Compute absolute change (not pct) over N days."""
    delta = {}
    for d, v in series.items():
        past = d - timedelta(days=days)
        if past in series:
            delta[d] = v - series[past]
    return delta


def _align_and_correlate(
    factor_series: dict[date, float],
    forward_returns: dict[date, float],
    lag: int,
) -> tuple[float | None, float | None]:
    """Compute Spearman rho between lagged factor and forward returns.

    Returns (rho, p_value) or (None, None) if insufficient data.
    """
    pairs_x = []
    pairs_y = []
    for d, ret in forward_returns.items():
        lagged_date = d - timedelta(days=lag)
        if lagged_date in factor_series:
            pairs_x.append(factor_series[lagged_date])
            pairs_y.append(ret)

    if len(pairs_x) < 30:
        return None, None

    x = np.array(pairs_x)
    y = np.array(pairs_y)

    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0, 1.0

    rho, p = spearmanr(x, y)
    if np.isfinite(rho):
        return float(rho), float(p)
    return None, None


def _best_correlation(
    factor_series: dict[date, float],
    forward_returns: dict[date, float],
) -> tuple[float | None, int, float | None]:
    """Find best |rho| across all lags. Returns (best_rho, best_lag, p_value)."""
    best_rho = None
    best_lag = LAGS[0]
    best_p = None
    for lag in LAGS:
        rho, p = _align_and_correlate(factor_series, forward_returns, lag)
        if rho is not None and (best_rho is None or abs(rho) > abs(best_rho)):
            best_rho = rho
            best_lag = lag
            best_p = p
    return best_rho, best_lag, best_p


def _compute_interaction_series(
    series_a: dict[date, float],
    series_b: dict[date, float],
) -> dict[date, float]:
    """Compute interaction term: product of rank-normalized (z-scored) series.

    Rank-normalizes each series to [0,1], then z-scores, then multiplies.
    This captures "when both factors move together" signals.
    """
    # Find common dates
    common_dates = sorted(set(series_a.keys()) & set(series_b.keys()))
    if len(common_dates) < 100:
        return {}

    vals_a = np.array([series_a[d] for d in common_dates])
    vals_b = np.array([series_b[d] for d in common_dates])

    # Rank-normalize to [0, 1]
    rank_a = rankdata(vals_a) / len(vals_a)
    rank_b = rankdata(vals_b) / len(vals_b)

    # Z-score the ranks
    za = (rank_a - np.mean(rank_a)) / (np.std(rank_a) or 1)
    zb = (rank_b - np.mean(rank_b)) / (np.std(rank_b) or 1)

    # Product = interaction
    interaction = za * zb

    return {d: float(v) for d, v in zip(common_dates, interaction)}


async def compute_correlations(engine) -> list[CorrelationResult]:
    """Compute Spearman rank correlation for each factor against SOL forward returns.

    Tests multiple modes per factor:
    - "returns": % change in factor vs SOL forward returns
    - "level": raw factor level vs SOL forward returns
    - "log_returns": log-transformed returns (for heavy-tailed factors)
    - "delta": 7-day absolute change (for factors in DELTA_FACTORS)

    Also tests interaction factors (pairwise products of rank-normalized base factors).

    Picks the mode with strongest |rho| for each factor.
    """
    sol_prices = await _load_raw_series(engine, "sol_ohlcv")
    if len(sol_prices) < MIN_DATA_POINTS:
        logger.warning(f"Only {len(sol_prices)} SOL price points, need {MIN_DATA_POINTS}")
        return []

    forward_returns = _compute_forward_returns(sol_prices, FORWARD_RETURN_DAYS)

    results = []
    # Store raw series for interaction computation
    raw_series: dict[str, dict[date, float]] = {}

    for source in FACTOR_SOURCES:
        raw_data = await _load_raw_series(engine, source)
        if len(raw_data) < MIN_DATA_POINTS:
            logger.info(f"Skipping {source}: only {len(raw_data)} data points (need {MIN_DATA_POINTS})")
            continue

        raw_series[source] = raw_data

        # Test all applicable modes
        candidates: list[tuple[str, dict[date, float]]] = []

        # Returns mode
        factor_returns = _compute_factor_returns(raw_data, FORWARD_RETURN_DAYS)
        candidates.append(("returns", factor_returns))

        # Level mode
        candidates.append(("level", raw_data))

        # Log-returns mode (for heavy-tailed factors)
        log_returns = _compute_log_returns(raw_data, FORWARD_RETURN_DAYS)
        if log_returns:
            candidates.append(("log_returns", log_returns))

        # Delta mode (for applicable factors)
        if source in DELTA_FACTORS:
            delta = _compute_delta(raw_data, days=7)
            if delta:
                candidates.append(("delta", delta))

        # Find best mode
        best_rho = None
        best_lag = LAGS[0]
        best_p = None
        best_mode = "returns"
        mode_details = []

        for mode_name, series in candidates:
            rho, lag, p = _best_correlation(series, forward_returns)
            if rho is not None:
                mode_details.append(f"{mode_name} rho={rho:.4f} lag={lag}d")
                if best_rho is None or abs(rho) > abs(best_rho):
                    best_rho = rho
                    best_lag = lag
                    best_p = p
                    best_mode = mode_name

        if best_rho is None:
            continue

        logger.info(f"[{source}] {' | '.join(mode_details)} | picked {best_mode} (rho={best_rho:.4f})")

        results.append(CorrelationResult(
            name=source,
            label=FACTOR_LABELS.get(source, source),
            correlation=round(best_rho, 4),
            optimal_lag_days=best_lag,
            weight=0.0,
            in_score=abs(best_rho) >= CORRELATION_THRESHOLD,
            mode=best_mode,
        ))

    # --- Interaction factors ---
    for src_a, src_b in INTERACTION_PAIRS:
        if src_a not in raw_series or src_b not in raw_series:
            continue

        interaction = _compute_interaction_series(raw_series[src_a], raw_series[src_b])
        if len(interaction) < MIN_DATA_POINTS:
            continue

        rho, lag, p = _best_correlation(interaction, forward_returns)
        if rho is None:
            continue

        name = f"{src_a}_x_{src_b}"
        label_a = FACTOR_LABELS.get(src_a, src_a)
        label_b = FACTOR_LABELS.get(src_b, src_b)
        label = f"{label_a} x {label_b}"

        logger.info(f"[{name}] interaction rho={rho:.4f} lag={lag}d p={p:.6f}")

        results.append(CorrelationResult(
            name=name,
            label=label,
            correlation=round(rho, 4),
            optimal_lag_days=lag,
            weight=0.0,
            in_score=abs(rho) >= CORRELATION_THRESHOLD,
            mode="interaction",
            components=[src_a, src_b],
        ))

    # Normalize weights for in_score factors
    scored = [r for r in results if r.in_score]
    if scored:
        total_abs_rho = sum(abs(r.correlation) for r in scored)
        for r in scored:
            r.weight = round(abs(r.correlation) / total_abs_rho, 4)

    return results
