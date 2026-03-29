"""Narrative pipeline: orchestrates scan -> filter -> classify -> aggregate -> lifecycle."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import get_session
from app.narrative.models import NarrativeToken, Narrative
from app.narrative.scanner import scan_trending_tokens
from app.narrative.filters import filter_duplicates, filter_scams
from app.narrative.classifier import classify_narratives

logger = logging.getLogger(__name__)


def compute_lifecycle(
    token_count: int,
    avg_gain: float,
    prev_volume: float,
    curr_volume: float,
) -> str:
    """Determine narrative lifecycle stage."""
    volume_growing = curr_volume > prev_volume * 0.8
    volume_collapsing = curr_volume < prev_volume * 0.5

    if token_count < 5 and volume_growing:
        return "emerging"
    if token_count >= 5 and avg_gain > 30 and volume_growing:
        return "trending"
    if avg_gain < 0 and volume_collapsing:
        return "fading"
    if token_count >= 5 and (avg_gain <= 30 or not volume_growing):
        return "saturated"
    return "fading"


async def run_narrative_pipeline(engine, http_client, groq_api_key: str) -> int:
    """Full pipeline: scan -> filter -> classify -> store -> aggregate.

    Returns number of tokens processed.
    """
    now = datetime.now(timezone.utc)

    # 1. Scan
    raw_tokens = await scan_trending_tokens(http_client)
    if not raw_tokens:
        return 0

    # 2. Filter duplicates
    tokens = filter_duplicates(raw_tokens)

    # 3. Filter scams
    tokens = await filter_scams(tokens, http_client)
    if not tokens:
        return 0

    # 4. Classify with Groq
    classifications = await classify_narratives(tokens, groq_api_key, http_client)

    # 5. Store tokens
    async with get_session(engine) as session:
        for t in tokens:
            narrative = classifications.get(t["address"], "Other")

            existing = (await session.execute(
                select(NarrativeToken).where(NarrativeToken.address == t["address"])
            )).scalar_one_or_none()

            if existing:
                existing.mcap = t.get("mcap")
                existing.price_change_pct = t.get("price_change_pct")
                existing.volume_24h = t.get("volume_24h")
                existing.liquidity_usd = t.get("liquidity_usd")
                existing.narrative = narrative
                existing.is_original = t.get("is_original", True)
                existing.parent_address = t.get("parent_address")
                existing.rugcheck_score = t.get("rugcheck_score")
                existing.last_seen = now
            else:
                created_at = t.get("created_at", now)
                session.add(NarrativeToken(
                    address=t["address"],
                    name=t["name"],
                    symbol=t["symbol"],
                    pair_address=t.get("pair_address", ""),
                    narrative=narrative,
                    mcap=t.get("mcap"),
                    price_change_pct=t.get("price_change_pct"),
                    volume_24h=t.get("volume_24h"),
                    liquidity_usd=t.get("liquidity_usd"),
                    is_original=t.get("is_original", True),
                    parent_address=t.get("parent_address"),
                    rugcheck_score=t.get("rugcheck_score"),
                    created_at=created_at,
                    first_seen=now,
                    last_seen=now,
                ))

        await session.commit()

    # 6. Aggregate narratives
    await _aggregate_narratives(engine, now)

    logger.info(f"Narrative pipeline processed {len(tokens)} tokens")
    return len(tokens)


async def _aggregate_narratives(engine, now: datetime):
    """Recompute narrative aggregates from current token data."""
    async with get_session(engine) as session:
        all_tokens = (await session.execute(select(NarrativeToken))).scalars().all()

        by_narrative: dict[str, list[NarrativeToken]] = {}
        for t in all_tokens:
            if t.narrative:
                by_narrative.setdefault(t.narrative, []).append(t)

        for name, tokens in by_narrative.items():
            gains = [t.price_change_pct for t in tokens if t.price_change_pct is not None]
            volumes = [t.volume_24h for t in tokens if t.volume_24h is not None]
            top = max(tokens, key=lambda t: t.price_change_pct or 0)

            avg_gain = sum(gains) / len(gains) if gains else 0
            total_vol = sum(volumes)

            existing = (await session.execute(
                select(Narrative).where(Narrative.name == name)
            )).scalar_one_or_none()

            prev_vol = existing.total_volume if existing else 0
            lifecycle = compute_lifecycle(len(tokens), avg_gain, prev_vol, total_vol)

            if existing:
                existing.token_count = len(tokens)
                existing.total_volume = total_vol
                existing.avg_gain_pct = avg_gain
                existing.top_token_address = top.address
                existing.lifecycle = lifecycle
                existing.last_updated = now
            else:
                session.add(Narrative(
                    name=name,
                    token_count=len(tokens),
                    total_volume=total_vol,
                    avg_gain_pct=avg_gain,
                    top_token_address=top.address,
                    lifecycle=lifecycle,
                    last_updated=now,
                ))

        await session.commit()
