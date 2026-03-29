"""Token verification: on-chain bonding curve check + RugCheck risk scoring."""
import base64
import logging
from datetime import datetime, timedelta, timezone

import httpx
from solders.pubkey import Pubkey
from sqlalchemy import select

from app.database import get_session
from app.launch.models import LaunchToken

logger = logging.getLogger(__name__)

PUMP_PROGRAM = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
BONDING_CURVE_DISCRIMINATOR = bytes([0x17, 0xB7, 0xF8, 0x37, 0x60, 0xD8, 0xAC, 0x60])

RUGCHECK_SUMMARY_URL = "https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary"

# Tokens verified per run (avoid rate limits)
VERIFY_BATCH_SIZE = 20
# RugCheck score threshold: lower is better, 0-1000 scale normalised
# Score of 0 = no risks, higher = more risky
RUGCHECK_MAX_SCORE = 500


async def verify_bonding_curve(mint_address: str, rpc_url: str, http_client: httpx.AsyncClient) -> bool:
    """Check if a token has a valid pump.fun bonding curve PDA on-chain."""
    try:
        mint = Pubkey.from_string(mint_address)
        pda, _ = Pubkey.find_program_address(
            [b"bonding-curve", bytes(mint)], PUMP_PROGRAM
        )

        resp = await http_client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [str(pda), {"encoding": "base64"}],
            },
            timeout=10.0,
        )
        data = resp.json()
        value = data.get("result", {}).get("value")
        if not value:
            return False

        account_data = base64.b64decode(value["data"][0])
        owner = value.get("owner", "")

        return (
            owner == str(PUMP_PROGRAM)
            and len(account_data) >= 8
            and account_data[:8] == BONDING_CURVE_DISCRIMINATOR
        )
    except Exception as e:
        logger.warning(f"Bonding curve check failed for {mint_address}: {e}")
        return False


async def get_rugcheck_score(mint_address: str, http_client: httpx.AsyncClient) -> int | None:
    """Fetch RugCheck risk score. Returns composite score where higher = riskier.

    Uses individual risk items rather than score_normalised, since the normalised
    score doesn't adequately flag bundled/concentrated tokens.

    Score thresholds:
    - 0: Clean (no risks)
    - 1-499: Minor risks (warn level)
    - 500+: Danger-level risks (single holder >20%, high concentration, etc.)
    """
    try:
        resp = await http_client.get(
            RUGCHECK_SUMMARY_URL.format(mint=mint_address), timeout=10.0
        )
        if resp.status_code != 200:
            return None
        data = resp.json()

        risks = data.get("risks", [])
        if not risks:
            return 0

        # If any risk is danger-level, return a high score to filter it out
        has_danger = any(r.get("level") == "danger" for r in risks)
        if has_danger:
            # Sum of all individual risk scores
            total = sum(r.get("score", 0) for r in risks)
            return max(total, 1000)  # Ensure it exceeds RUGCHECK_MAX_SCORE

        # Warn-level risks: sum their scores
        return sum(r.get("score", 0) for r in risks)
    except Exception as e:
        logger.warning(f"RugCheck failed for {mint_address}: {e}")
        return None


async def verify_tokens(engine, http_client: httpx.AsyncClient, rpc_url: str) -> int:
    """Verify unverified tokens: bonding curve PDA + RugCheck score.

    Processes tokens in small batches to stay within rate limits.
    Returns number of tokens verified this run.
    """
    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchToken)
            .where(LaunchToken.verified_pumpfun.is_(None))
            .where(LaunchToken.launchpad.is_not(None))
            .order_by(LaunchToken.created_at.desc())
            .limit(VERIFY_BATCH_SIZE)
        )
        tokens = result.scalars().all()

    if not tokens:
        return 0

    verified_count = 0
    async with get_session(engine) as session:
        # Re-load within session for updates
        result = await session.execute(
            select(LaunchToken).where(
                LaunchToken.address.in_([t.address for t in tokens])
            )
        )
        to_update = result.scalars().all()

        for token in to_update:
            # pump.fun tokens: verify bonding curve PDA on-chain
            # Other launchpads: skip PDA check (not applicable), mark as valid
            if token.launchpad == "pumpfun":
                is_valid = await verify_bonding_curve(token.address, rpc_url, http_client)
            else:
                is_valid = True  # Non-pump tokens identified by DEX, not PDA

            token.verified_pumpfun = is_valid

            if is_valid:
                score = await get_rugcheck_score(token.address, http_client)
                token.rugcheck_score = score

            verified_count += 1

        await session.commit()

    if verified_count:
        logger.info(
            f"Verified {verified_count} token(s) "
            f"({sum(1 for t in to_update if t.verified_pumpfun)} passed)"
        )
    return verified_count
