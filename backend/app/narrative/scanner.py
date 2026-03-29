"""DexScreener scanner: fetches trending Solana tokens for narrative classification."""
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/tokens/v1/solana"
BATCH_SIZE = 30  # DexScreener limit per request


async def scan_trending_tokens(http_client: httpx.AsyncClient) -> list[dict]:
    """Fetch trending Solana tokens from DexScreener.

    Two-step process:
    1. Get boosted/trending token addresses from the boosts endpoint
    2. Batch-fetch their trading data (mcap, volume, price change) from the tokens endpoint

    Returns list of dicts with: address, name, symbol, pair_address,
    mcap, price_change_pct, volume_24h, liquidity_usd, created_at.
    """
    # Step 1: Get trending token addresses
    try:
        resp = await http_client.get(DEXSCREENER_BOOSTS_URL, timeout=15.0)
        resp.raise_for_status()
        boosts = resp.json()
    except Exception as e:
        logger.warning(f"DexScreener boosts fetch failed: {e}")
        return []

    if not isinstance(boosts, list):
        return []

    addresses = [
        b["tokenAddress"] for b in boosts
        if b.get("chainId") == "solana" and b.get("tokenAddress")
    ]

    if not addresses:
        return []

    # Step 2: Batch-fetch trading data
    all_pairs = []
    for i in range(0, len(addresses), BATCH_SIZE):
        batch = addresses[i : i + BATCH_SIZE]
        url = f"{DEXSCREENER_TOKENS_URL}/{','.join(batch)}"
        try:
            resp = await http_client.get(url, timeout=15.0)
            resp.raise_for_status()
            pairs = resp.json()
            if isinstance(pairs, list):
                all_pairs.extend(pairs)
        except Exception as e:
            logger.warning(f"DexScreener token batch failed: {e}")
            continue

    # Deduplicate by token address (take first/most active pair per token)
    tokens = []
    seen = set()
    for pair in all_pairs:
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
