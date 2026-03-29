"""DexScreener scanner: fetches trending Solana tokens for narrative classification."""
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"


async def scan_trending_tokens(http_client: httpx.AsyncClient) -> list[dict]:
    """Fetch trending Solana tokens from DexScreener.

    Returns list of dicts with: address, name, symbol, pair_address,
    mcap, price_change_pct, volume_24h, liquidity_usd, created_at.
    """
    try:
        resp = await http_client.get(DEXSCREENER_BOOSTS_URL, timeout=15.0)
        resp.raise_for_status()
        pairs = resp.json()
    except Exception as e:
        logger.warning(f"DexScreener trending fetch failed: {e}")
        return []

    if not isinstance(pairs, list):
        return []

    tokens = []
    seen = set()
    for pair in pairs:
        if pair.get("chainId") != "solana":
            continue

        base = pair.get("baseToken") or {}
        address = base.get("address", "")
        if not address or address in seen:
            continue
        seen.add(address)

        volume = pair.get("volume") or {}
        liquidity = pair.get("liquidity") or {}
        price_change = pair.get("priceChange") or {}
        created_ms = pair.get("pairCreatedAt")

        created_at = (
            datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            if created_ms
            else datetime.now(timezone.utc)
        )

        tokens.append({
            "address": address,
            "name": base.get("name", ""),
            "symbol": base.get("symbol", ""),
            "pair_address": pair.get("pairAddress", ""),
            "mcap": pair.get("marketCap") or 0,
            "price_change_pct": price_change.get("h24") or 0,
            "volume_24h": volume.get("h24") or 0,
            "liquidity_usd": liquidity.get("usd") or 0,
            "created_at": created_at,
        })

    logger.info(f"Scanned {len(tokens)} trending Solana tokens")
    return tokens
