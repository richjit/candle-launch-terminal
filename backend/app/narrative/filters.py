"""Duplicate detection and scam filtering for narrative tokens."""
import logging

import httpx

logger = logging.getLogger(__name__)

RUGCHECK_SUMMARY_URL = "https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary"
MIN_LIQUIDITY = 1000  # $1K minimum
RUGCHECK_MAX_SCORE = 500


def filter_duplicates(tokens: list[dict]) -> list[dict]:
    """Detect duplicate tokens by exact name match. Oldest = original, rest = forks."""
    by_name: dict[str, list[dict]] = {}
    for t in tokens:
        name = t["name"].strip().lower()
        by_name.setdefault(name, []).append(t)

    result = []
    for name, group in by_name.items():
        group.sort(key=lambda t: t.get("created_at", ""))
        original = group[0]
        original["is_original"] = True
        original["parent_address"] = None
        result.append(original)
        for fork in group[1:]:
            fork["is_original"] = False
            fork["parent_address"] = original["address"]
            result.append(fork)

    return result


async def filter_scams(
    tokens: list[dict], http_client: httpx.AsyncClient
) -> list[dict]:
    """Filter out scam tokens using RugCheck API."""
    clean = []
    for token in tokens:
        if token.get("liquidity_usd", 0) < MIN_LIQUIDITY:
            continue

        try:
            resp = await http_client.get(
                RUGCHECK_SUMMARY_URL.format(mint=token["address"]), timeout=10.0
            )
            if resp.status_code != 200:
                clean.append(token)
                continue

            data = resp.json()
            risks = data.get("risks", [])
            has_danger = any(r.get("level") == "danger" for r in risks)
            if has_danger:
                total_score = sum(r.get("score", 0) for r in risks)
                if total_score > RUGCHECK_MAX_SCORE:
                    logger.debug(f"Filtered scam: {token['name']} (score={total_score})")
                    continue

            token["rugcheck_score"] = sum(r.get("score", 0) for r in risks)
            clean.append(token)
        except Exception:
            clean.append(token)

    return clean
