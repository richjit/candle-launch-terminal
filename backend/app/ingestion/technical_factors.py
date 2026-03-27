# backend/app/ingestion/technical_factors.py
"""
Compute technical factors from SOL OHLCV data and store in historical_data.

Currently computes:
- vol_regime: Inverted Garman-Klass volatility percentile rank (0-100).
  High values = low volatility = healthy trending market.
  Low values = high volatility = stressed/uncertain market.
"""
import json
import logging
import math
from datetime import date

import numpy as np
from sqlalchemy import select, func

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)

VOL_WINDOW = 14        # days for Garman-Klass vol estimate
RANK_LOOKBACK = 90     # days for percentile ranking
SOURCE = "vol_regime"


def _garman_klass_vol(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> float:
    """Garman-Klass volatility estimator (annualized).

    More efficient than close-to-close because it uses intraday range (OHLC).
    Formula: σ² = 0.5 * ln(H/L)² - (2ln2 - 1) * ln(C/O)²
    """
    n = len(opens)
    if n == 0:
        return 0.0
    log_hl = np.log(highs / lows)
    log_co = np.log(closes / opens)
    gk = 0.5 * log_hl**2 - (2 * math.log(2) - 1) * log_co**2
    daily_var = float(np.mean(gk))
    # Annualize: sqrt(252 * daily_variance)
    return math.sqrt(max(0, daily_var) * 252)


async def compute_vol_regime(engine) -> int:
    """Compute inverted vol percentile for each date and store in historical_data.

    Returns number of rows inserted (0 if already computed).
    """
    async with get_session(engine) as session:
        result = await session.execute(
            select(func.count()).select_from(HistoricalData).where(HistoricalData.source == SOURCE)
        )
        if result.scalar() > 0:
            logger.info(f"{SOURCE} already computed, skipping")
            return 0

    # Load all SOL OHLCV data
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData)
            .where(HistoricalData.source == "sol_ohlcv")
            .order_by(HistoricalData.date)
        )
        rows = result.scalars().all()

    if len(rows) < VOL_WINDOW + RANK_LOOKBACK:
        logger.warning(f"Not enough OHLCV data for vol_regime ({len(rows)} rows)")
        return 0

    # Extract OHLC arrays
    dates: list[date] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []

    for row in rows:
        meta = json.loads(row.metadata_json) if row.metadata_json else {}
        dates.append(row.date)
        opens.append(meta.get("open", row.value))
        highs.append(meta.get("high", row.value))
        lows.append(meta.get("low", row.value))
        closes.append(meta.get("close", row.value))

    opens_arr = np.array(opens)
    highs_arr = np.array(highs)
    lows_arr = np.array(lows)
    closes_arr = np.array(closes)

    # Compute rolling Garman-Klass vol for each day
    n = len(dates)
    gk_vols = np.full(n, np.nan)
    for i in range(VOL_WINDOW, n):
        start = i - VOL_WINDOW
        gk_vols[i] = _garman_klass_vol(
            opens_arr[start:i], highs_arr[start:i], lows_arr[start:i], closes_arr[start:i]
        )

    # Compute percentile rank of each day's vol vs trailing RANK_LOOKBACK days
    # Then INVERT: low vol = high score (healthy market)
    rows_to_insert = []
    min_idx = VOL_WINDOW + RANK_LOOKBACK
    for i in range(min_idx, n):
        current_vol = gk_vols[i]
        if np.isnan(current_vol):
            continue

        # Trailing vol values for ranking
        lookback_vols = gk_vols[i - RANK_LOOKBACK:i]
        valid_vols = lookback_vols[~np.isnan(lookback_vols)]
        if len(valid_vols) < 30:
            continue

        # Percentile rank: what fraction of trailing vols are <= current
        # High value = high vol (stressed market), low value = low vol (healthy)
        # The correlation engine determines the sign relationship with SOL returns
        pct_rank = float(np.sum(valid_vols <= current_vol) / len(valid_vols))
        pct_score = pct_rank * 100.0

        rows_to_insert.append(HistoricalData(
            source=SOURCE,
            date=dates[i],
            value=round(pct_score, 2),
            metadata_json=json.dumps({
                "gk_vol_annualized": round(current_vol, 4),
                "vol_percentile": round(pct_score, 1),
            }),
        ))

    async with get_session(engine) as session:
        session.add_all(rows_to_insert)
        await session.commit()

    logger.info(f"Computed {len(rows_to_insert)} {SOURCE} data points")
    return len(rows_to_insert)
