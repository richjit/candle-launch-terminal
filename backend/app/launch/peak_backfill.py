"""Backfill actual peak market cap from GeckoTerminal OHLCV candle data.

DexScreener polling (every 2 min) misses the real peak for most pump.fun tokens
because they spike and dump within seconds of migration. This module fetches
1-minute OHLCV candles for each token's first hour and computes the true peak mcap.
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.database import get_session
from app.launch.config import BONDING_CURVE_DEXES
from app.launch.models import LaunchToken

logger = logging.getLogger(__name__)

GECKO_OHLCV_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/hour"
)
DEXSCREENER_TOKEN_URL = "https://api.dexscreener.com/tokens/v1/solana/{address}"

# pump.fun tokens have 1 billion total supply
PUMPFUN_SUPPLY = 1_000_000_000

# Process this many tokens per run (GeckoTerminal: 30 calls/min free tier)
BACKFILL_BATCH_SIZE = 15

# Minimum age before backfilling (need enough candle data)
MIN_AGE = timedelta(minutes=30)


async def _get_best_pair_info(
    token_address: str, http_client: httpx.AsyncClient
) -> dict | None:
    """Get the most active pair info for a token from DexScreener.

    Returns dict with pairAddress, marketCap, priceUsd, or None.
    """
    try:
        resp = await http_client.get(
            DEXSCREENER_TOKEN_URL.format(address=token_address), timeout=10.0
        )
        if resp.status_code != 200:
            return None
        pairs = resp.json()
        if not isinstance(pairs, list) or not pairs:
            return None
        p = pairs[0]
        return {
            "pairAddress": p.get("pairAddress"),
            "marketCap": p.get("marketCap") or p.get("fdv"),
            "priceUsd": float(p["priceUsd"]) if p.get("priceUsd") else None,
            "pairCreatedAt": p.get("pairCreatedAt"),
        }
    except Exception:
        return None


async def _fetch_peak_data(
    pair_address: str,
    http_client: httpx.AsyncClient,
) -> tuple[float | None, int | None]:
    """Fetch OHLCV candles and return (highest credible price, peak timestamp).

    Uses 5-minute candles with a 100-candle limit (~8 hours of data) to capture
    peaks that happen after initial launch. Filters out candles with near-zero
    volume to avoid inflated prices from thin pools.
    """
    try:
        url = GECKO_OHLCV_URL.format(pool=pair_address)
        resp = await http_client.get(
            url,
            params={
                "aggregate": 1,  # 1-hour candles
                "limit": 100,  # ~4 days of coverage
                "currency": "usd",
            },
            headers={"Accept": "application/json"},
            timeout=15.0,
        )

        if resp.status_code != 200:
            return None, None

        data = resp.json()
        candles = data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])

        if not candles:
            return None, None

        # Each candle: [timestamp, open, high, low, close, volume_usd]
        # Only trust highs from candles with at least $10 volume
        MIN_CANDLE_VOLUME = 10.0
        credible = [
            (c[2], c[0]) for c in candles
            if c[2] and c[2] > 0 and len(c) > 5 and (c[5] or 0) >= MIN_CANDLE_VOLUME
        ]

        if not credible:
            credible = [
                (c[2], c[0]) for c in candles
                if c[2] and c[2] > 0 and len(c) > 5 and (c[5] or 0) > 0
            ]

        if not credible:
            return None, None

        best = max(credible, key=lambda x: x[0])
        return best[0], best[1]

    except Exception as e:
        logger.warning(f"OHLCV fetch failed for {pair_address}: {e}")
        return None, None


async def backfill_peak_mcaps(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch OHLCV candles for tokens that need peak backfilling.

    Targets tokens that are old enough to have first-hour candle data
    but haven't been backfilled yet. Updates mcap_peak_1h with the
    true peak derived from candle highs.

    Returns number of tokens updated.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - MIN_AGE

    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchToken)
            .where(LaunchToken.peak_backfilled == False)  # noqa: E712
            .where(LaunchToken.created_at <= cutoff)
            .where(LaunchToken.pair_address.is_not(None))
            .where(LaunchToken.dex.not_in(BONDING_CURVE_DEXES))
            .order_by(LaunchToken.mcap_peak_1h.desc().nullslast())
            .limit(BACKFILL_BATCH_SIZE)
        )
        tokens = list(result.scalars().all())

    if not tokens:
        return 0

    updated = 0
    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchToken).where(
                LaunchToken.address.in_([t.address for t in tokens])
            )
        )
        to_update = result.scalars().all()

        for token in to_update:
            # Get DexScreener info for the most active pair
            pair_info = await _get_best_pair_info(token.address, http_client)
            best_pair = pair_info["pairAddress"] if pair_info else None
            pair_to_query = best_pair or token.pair_address

            peak_price, peak_ts = await _fetch_peak_data(pair_to_query, http_client)

            if peak_price is not None:
                # Compute peak mcap using price ratio * current FDV
                # This works for any token supply, not just 1B pump.fun tokens
                current_price = pair_info.get("priceUsd") if pair_info else None
                current_mcap = pair_info.get("marketCap") if pair_info else None

                if current_price and current_price > 0 and current_mcap:
                    ohlcv_peak = current_mcap * (peak_price / current_price)
                else:
                    # Fallback to 1B supply assumption for pump.fun tokens
                    ohlcv_peak = peak_price * PUMPFUN_SUPPLY

                old_peak = token.mcap_peak_1h or 0

                # Always use OHLCV from the most active pair as the authoritative peak.
                if ohlcv_peak != old_peak:
                    token.mcap_peak_1h = ohlcv_peak
                    logger.debug(
                        f"Peak backfill {token.address[:12]}: "
                        f"${old_peak:,.0f} -> ${ohlcv_peak:,.0f}"
                    )

                # Compute time_to_peak from the actual candle timestamp
                # Use DexScreener pairCreatedAt as mint time (more accurate than our discovery time)
                if peak_ts is not None:
                    pair_created_ms = pair_info.get("pairCreatedAt") if pair_info else None
                    if pair_created_ms:
                        mint_time = datetime.fromtimestamp(pair_created_ms / 1000, tz=timezone.utc)
                    else:
                        mint_time = token.created_at
                        if mint_time.tzinfo is None:
                            mint_time = mint_time.replace(tzinfo=timezone.utc)
                    peak_dt = datetime.fromtimestamp(peak_ts, tz=timezone.utc)
                    delta = peak_dt - mint_time
                    token.time_to_peak_minutes = max(0, int(delta.total_seconds() / 60))

            # Update pair_address to the most active pool
            if best_pair and best_pair != token.pair_address:
                token.pair_address = best_pair

            token.peak_backfilled = True
            updated += 1

        if updated:
            await session.commit()
            logger.info(f"Backfilled peak mcap for {updated} token(s)")

    return updated
