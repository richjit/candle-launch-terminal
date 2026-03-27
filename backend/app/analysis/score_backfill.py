import json
import logging
import math
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select, func

from app.database import get_session, HistoricalData, DailyScore
from app.analysis.correlation import CorrelationResult, _load_series

logger = logging.getLogger(__name__)

ROLLING_WINDOW = 90


async def backfill_scores(engine, correlations: list[CorrelationResult]) -> int:
    """Compute historical daily scores and store in daily_scores table.

    Uses 90-day rolling mean/std for z-score computation.
    Returns number of rows inserted (0 if already backfilled).
    """
    # Check if already backfilled
    async with get_session(engine) as session:
        result = await session.execute(select(func.count()).select_from(DailyScore))
        if result.scalar() > 0:
            logger.info("Daily scores already backfilled, skipping")
            return 0

    scored_factors = [c for c in correlations if c.in_score]
    if not scored_factors:
        logger.warning("No scored factors available for backfill")
        return 0

    # Load all factor data using _load_series (handles delta transforms for stablecoin_supply)
    factor_series: dict[str, dict[date, float]] = {}
    for factor in scored_factors:
        factor_series[factor.name] = await _load_series(engine, factor.name)

    # Load SOL price dates to know which days to score
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData.date)
            .where(HistoricalData.source == "sol_ohlcv")
            .order_by(HistoricalData.date)
        )
        all_dates = [row.date for row in result.all()]

    # Need at least ROLLING_WINDOW days before we can compute z-scores
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

        for factor in scored_factors:
            series = factor_series.get(factor.name, {})
            current_val = series.get(current_date)
            if current_val is None:
                continue

            # Compute rolling stats over window
            window_vals = [series.get(d) for d in window_dates if d in series]
            if len(window_vals) < 30:  # need minimum window data
                continue

            arr = np.array(window_vals)
            mean = float(np.mean(arr))
            std = float(np.std(arr))
            if std == 0:
                z_score = 0.0
            else:
                z_score = (current_val - mean) / std

            # sign(r) * |weight| * z_score
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

        if factors_available == 0:
            continue

        # Pass weighted z-sum directly into tanh (weights already sum to 1.0)
        score = 50 + 50 * math.tanh(weighted_z_sum / 2)
        score = max(0, min(100, score))

        scores_to_insert.append(DailyScore(
            date=current_date,
            score=round(score, 1),
            factors_json=json.dumps(factors_json),
            factors_available=factors_available,
            factors_total=len(scored_factors),
        ))

    # Batch insert
    async with get_session(engine) as session:
        session.add_all(scores_to_insert)
        await session.commit()

    logger.info(f"Backfilled {len(scores_to_insert)} daily scores")
    return len(scores_to_insert)
