import json
import logging
import math
from datetime import date, timedelta

import numpy as np
from scipy.stats import rankdata
from sqlalchemy import select, func

from app.database import get_session, HistoricalData, DailyScore
from app.analysis.correlation import (
    CorrelationResult, _load_raw_series, _load_series,
    _compute_interaction_series,
)

logger = logging.getLogger(__name__)

ROLLING_WINDOW = 90


async def backfill_scores(engine, correlations: list[CorrelationResult]) -> int:
    """Compute historical daily scores and store in daily_scores table.

    Uses 90-day rolling z-scores for base factors.
    For interaction factors, computes rank-normalized product of components.
    Returns number of rows inserted (0 if already backfilled).
    """
    async with get_session(engine) as session:
        result = await session.execute(select(func.count()).select_from(DailyScore))
        if result.scalar() > 0:
            logger.info("Daily scores already backfilled, skipping")
            return 0

    scored_factors = [c for c in correlations if c.in_score]
    if not scored_factors:
        logger.warning("No scored factors available for backfill")
        return 0

    # Separate base factors from interaction factors
    base_factors = [f for f in scored_factors if f.mode != "interaction"]
    interaction_factors = [f for f in scored_factors if f.mode == "interaction"]

    # Load base factor data
    factor_series: dict[str, dict[date, float]] = {}
    raw_series: dict[str, dict[date, float]] = {}
    for factor in base_factors:
        # For scoring, use the mode-appropriate series
        if factor.mode in ("returns", "log_returns"):
            # For return-based modes, we still z-score the raw/delta values
            # because the score uses rolling z-scores of the factor level,
            # with the correlation sign determining direction
            factor_series[factor.name] = await _load_series(engine, factor.name)
        else:
            factor_series[factor.name] = await _load_series(engine, factor.name)

    # Load raw series for interaction factors
    needed_raw = set()
    for f in interaction_factors:
        for comp in f.components:
            needed_raw.add(comp)
    for source in needed_raw:
        if source not in raw_series:
            raw_series[source] = await _load_raw_series(engine, source)

    # Pre-compute interaction series
    interaction_series: dict[str, dict[date, float]] = {}
    for factor in interaction_factors:
        if len(factor.components) == 2:
            src_a, src_b = factor.components
            if src_a in raw_series and src_b in raw_series:
                interaction_series[factor.name] = _compute_interaction_series(
                    raw_series[src_a], raw_series[src_b]
                )

    # Load SOL price dates to know which days to score
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData.date)
            .where(HistoricalData.source == "sol_ohlcv")
            .order_by(HistoricalData.date)
        )
        all_dates = [row.date for row in result.all()]

    if len(all_dates) < ROLLING_WINDOW:
        logger.warning(f"Only {len(all_dates)} dates, need at least {ROLLING_WINDOW}")
        return 0

    scores_to_insert = []
    for idx in range(ROLLING_WINDOW, len(all_dates)):
        current_date = all_dates[idx]
        window_start_idx = idx - ROLLING_WINDOW
        window_dates = all_dates[window_start_idx:idx]

        factors_json = {}
        weighted_z_sum = 0.0
        total_weight = 0.0
        factors_available = 0

        # Score base factors
        for factor in base_factors:
            series = factor_series.get(factor.name, {})
            current_val = series.get(current_date)
            if current_val is None:
                continue

            window_vals = [series.get(d) for d in window_dates if d in series]
            if len(window_vals) < 30:
                continue

            arr = np.array(window_vals)
            mean = float(np.mean(arr))
            std = float(np.std(arr))
            if std == 0:
                z_score = 0.0
            else:
                z_score = (current_val - mean) / std

            signed_contribution = math.copysign(1, factor.correlation) * factor.weight * z_score
            weighted_z_sum += signed_contribution
            total_weight += factor.weight
            factors_available += 1

            factors_json[factor.name] = {
                "value": current_val,
                "z_score": round(z_score, 4),
                "weight": factor.weight,
                "contribution": round(signed_contribution, 4),
            }

        # Score interaction factors
        for factor in interaction_factors:
            series = interaction_series.get(factor.name, {})
            current_val = series.get(current_date)
            if current_val is None:
                continue

            window_vals = [series.get(d) for d in window_dates if d in series]
            if len(window_vals) < 30:
                continue

            arr = np.array(window_vals)
            mean = float(np.mean(arr))
            std = float(np.std(arr))
            if std == 0:
                z_score = 0.0
            else:
                z_score = (current_val - mean) / std

            signed_contribution = math.copysign(1, factor.correlation) * factor.weight * z_score
            weighted_z_sum += signed_contribution
            total_weight += factor.weight
            factors_available += 1

            factors_json[factor.name] = {
                "value": round(current_val, 4),
                "z_score": round(z_score, 4),
                "weight": factor.weight,
                "contribution": round(signed_contribution, 4),
            }

        if factors_available == 0:
            continue

        score = 50 + 50 * math.tanh(weighted_z_sum / 2)
        score = max(0, min(100, score))

        scores_to_insert.append(DailyScore(
            date=current_date,
            score=round(score, 1),
            factors_json=json.dumps(factors_json),
            factors_available=factors_available,
            factors_total=len(scored_factors),
        ))

    async with get_session(engine) as session:
        session.add_all(scores_to_insert)
        await session.commit()

    logger.info(f"Backfilled {len(scores_to_insert)} daily scores")
    return len(scores_to_insert)
