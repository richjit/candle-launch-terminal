"""GeckoTerminal discovery: polls for new Solana pools and creates LaunchToken rows."""
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.database import get_session
from app.launch.config import identify_launchpad
from app.launch.models import LaunchToken

logger = logging.getLogger(__name__)

GECKO_NEW_POOLS_URL = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools"


def _parse_token_address(token_id: str) -> str:
    """Extract mint address from GeckoTerminal token ID like 'solana_MintAddr123'."""
    return token_id.removeprefix("solana_")


def _parse_dex_id(dex_data: dict) -> str:
    """Extract DEX id from GeckoTerminal relationship."""
    return dex_data.get("data", {}).get("id", "")


async def discover_new_launches(engine, http_client: httpx.AsyncClient) -> int:
    """Poll GeckoTerminal for new Solana pools and insert launchpad tokens.

    Returns number of new tokens created.
    """
    try:
        resp = await http_client.get(GECKO_NEW_POOLS_URL, timeout=15.0)
        resp.raise_for_status()
        data = await resp.json()
    except Exception as e:
        logger.warning(f"GeckoTerminal discovery failed: {e}")
        return 0

    pools = data.get("data", [])
    if not pools:
        return 0

    new_count = 0
    async with get_session(engine) as session:
        # Batch-check which addresses already exist
        candidate_addresses = []
        candidate_pools = []
        for pool in pools:
            rels = pool.get("relationships", {})
            base_token = rels.get("base_token", {})
            token_id = base_token.get("data", {}).get("id", "")
            if not token_id:
                continue

            address = _parse_token_address(token_id)
            dex_id = _parse_dex_id(rels.get("dex", {}))
            attrs = pool.get("attributes", {})
            dex_name = dex_id  # GeckoTerminal uses dex id as name

            launchpad = identify_launchpad(
                dex_name=dex_name,
                token_address=address,
                dex_id=dex_id,
            )
            if not launchpad:
                continue

            candidate_addresses.append(address)
            candidate_pools.append((address, pool, launchpad, dex_id, attrs))

        if not candidate_addresses:
            return 0

        # Check existing
        result = await session.execute(
            select(LaunchToken.address).where(
                LaunchToken.address.in_(candidate_addresses)
            )
        )
        existing = set(result.scalars().all())

        for address, pool, launchpad, dex_id, attrs in candidate_pools:
            if address in existing:
                continue

            pool_address = attrs.get("address", "")
            created_str = attrs.get("pool_created_at", "")
            try:
                created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                created_at = datetime.now(timezone.utc)

            token = LaunchToken(
                address=address,
                pair_address=pool_address,
                launchpad=launchpad,
                dex=dex_id,
                created_at=created_at,
            )
            session.add(token)
            new_count += 1

        if new_count:
            await session.commit()
            logger.info(f"Discovered {new_count} new launchpad token(s)")

    return new_count
