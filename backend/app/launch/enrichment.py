"""DexScreener enrichment: batch-updates tracked tokens with performance data."""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.database import get_session
from app.launch.models import LaunchToken

logger = logging.getLogger(__name__)

DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/tokens/v1/solana"
BATCH_SIZE = 30
ALIVE_VOLUME_THRESHOLD = 100.0  # $100/hr minimum


async def enrich_tracked_tokens(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch DexScreener data for all non-complete tokens and update their metrics.

    Returns the number of tokens updated.
    """
    now = datetime.now(timezone.utc)

    # Load addresses of tokens that still need updates
    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchToken.address).where(LaunchToken.checkpoint_complete == False)  # noqa: E712
        )
        addresses = list(result.scalars().all())

    if not addresses:
        return 0

    # Batch fetch from DexScreener
    all_pairs = []
    for i in range(0, len(addresses), BATCH_SIZE):
        batch = addresses[i : i + BATCH_SIZE]
        url = f"{DEXSCREENER_TOKENS_URL}/{','.join(batch)}"
        try:
            resp = await http_client.get(url, timeout=15.0)
            resp.raise_for_status()
            pairs = resp.json()  # NOTE: httpx .json() is synchronous
            if isinstance(pairs, list):
                all_pairs.extend(pairs)
        except Exception as e:
            logger.warning(f"DexScreener enrichment batch failed: {e}")
            continue

    if not all_pairs:
        return 0

    # Index pairs by base token address (take first pair per token)
    pair_by_token: dict[str, dict] = {}
    for pair in all_pairs:
        addr = pair.get("baseToken", {}).get("address", "")
        if addr and addr not in pair_by_token:
            pair_by_token[addr] = pair

    updated = 0
    async with get_session(engine) as session:
        # Re-load tokens within this session for updates
        result = await session.execute(
            select(LaunchToken).where(LaunchToken.checkpoint_complete == False)  # noqa: E712
        )
        tokens_to_update = result.scalars().all()

        for token in tokens_to_update:
            pair = pair_by_token.get(token.address)
            if not pair:
                continue

            # SQLite stores naive datetimes; normalize to UTC for comparison
            created_at = token.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age = now - created_at
            mcap = pair.get("marketCap") or 0
            volume = pair.get("volume", {})
            txns = pair.get("txns", {})
            liq = pair.get("liquidity", {})

            vol_h1 = volume.get("h1", 0) or 0
            vol_h24 = volume.get("h24", 0) or 0

            buys_h1 = txns.get("h1", {}).get("buys", 0) or 0
            sells_h1 = txns.get("h1", {}).get("sells", 0) or 0
            buys_h24 = txns.get("h24", {}).get("buys", 0) or 0
            sells_h24 = txns.get("h24", {}).get("sells", 0) or 0

            liquidity_usd = liq.get("usd", 0) or 0

            # Update current data
            token.mcap_current = mcap
            token.liquidity_usd = liquidity_usd
            token.is_alive = vol_h1 >= ALIVE_VOLUME_THRESHOLD
            token.last_updated = now

            # Track peak mcap within checkpoint windows
            # IMPORTANT: Save old peak BEFORE updating so we can detect new peaks
            if age <= timedelta(hours=1):
                old_peak_1h = token.mcap_peak_1h or 0
                token.mcap_peak_1h = max(old_peak_1h, mcap)
            elif token.mcap_peak_1h is None:
                token.mcap_peak_1h = mcap

            if age <= timedelta(hours=24):
                old_peak_24h = token.mcap_peak_24h or 0
                token.mcap_peak_24h = max(old_peak_24h, mcap)
                # Update time_to_peak only if this is a NEW peak
                if mcap > old_peak_24h:
                    token.time_to_peak_minutes = int(age.total_seconds() / 60)
            elif token.mcap_peak_24h is None:
                token.mcap_peak_24h = mcap

            if age <= timedelta(days=7):
                old_peak_7d = token.mcap_peak_7d or 0
                token.mcap_peak_7d = max(old_peak_7d, mcap)
            elif token.mcap_peak_7d is None:
                token.mcap_peak_7d = mcap

            # Snapshot checkpoint metrics at the right times
            # NOTE: DexScreener's h1/h24 are rolling windows from "now", not from
            # the token's creation time. These are approximations.
            if age >= timedelta(hours=1) and token.volume_1h is None:
                token.volume_1h = vol_h1
                token.buys_1h = buys_h1
                token.sells_1h = sells_h1

            if age >= timedelta(hours=24) and token.volume_24h is None:
                token.volume_24h = vol_h24
                token.buys_24h = buys_h24
                token.sells_24h = sells_h24

            if age >= timedelta(days=7) and token.volume_7d is None:
                # DexScreener has no 7d volume field — use h24 at 7d mark as proxy
                token.volume_7d = volume.get("h24", 0)
                token.checkpoint_complete = True

            updated += 1

        if updated:
            await session.commit()
            logger.info(f"Enriched {updated} token(s) via DexScreener")

    return updated
