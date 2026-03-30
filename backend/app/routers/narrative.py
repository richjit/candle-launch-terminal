"""API endpoints for the Narrative Tracker."""
import logging
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.database import get_session
from app.narrative.models import NarrativeToken, Narrative

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/narrative", tags=["narrative"])

_engine = None


def set_engine(engine):
    global _engine
    _engine = engine


@router.get("/overview")
async def get_overview():
    """All narratives ranked by momentum + top 10 runners."""
    async with get_session(_engine) as session:
        narratives = (await session.execute(
            select(Narrative)
            .where(Narrative.token_count >= 2)
            .where(Narrative.total_volume >= 10000)
            .order_by((Narrative.avg_gain_pct * Narrative.total_volume).desc())
        )).scalars().all()

        # Top runners: must have real traction (mcap > $5K)
        runners = (await session.execute(
            select(NarrativeToken)
            .where(NarrativeToken.price_change_pct.is_not(None))
            .where(NarrativeToken.mcap > 5000)
            .order_by(NarrativeToken.price_change_pct.desc())
            .limit(10)
        )).scalars().all()

    return {
        "narratives": [
            {
                "name": n.name,
                "token_count": n.token_count,
                "total_volume": n.total_volume,
                "total_mcap": n.total_mcap,
                "avg_mcap": n.avg_mcap,
                "avg_gain_pct": n.avg_gain_pct,
                "lifecycle": n.lifecycle,
                "top_token_address": n.top_token_address,
                "last_updated": n.last_updated.isoformat() if n.last_updated else None,
            }
            for n in narratives
        ],
        "top_runners": [
            {
                "address": t.address,
                "name": t.name,
                "symbol": t.symbol,
                "narrative": t.narrative,
                "mcap": t.mcap,
                "mcap_ath": t.mcap_ath,
                "price_change_pct": t.price_change_pct,
                "volume_24h": t.volume_24h,
                "liquidity_usd": t.liquidity_usd,
                "is_original": t.is_original,
                "parent_address": t.parent_address,
                "pair_address": t.pair_address,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in runners
        ],
    }


@router.get("/{name:path}")
async def get_narrative_detail(name: str):
    """Detail view for one narrative with all its tokens."""
    async with get_session(_engine) as session:
        narrative = (await session.execute(
            select(Narrative).where(Narrative.name == name)
        )).scalar_one_or_none()

        if not narrative:
            raise HTTPException(status_code=404, detail=f"Narrative '{name}' not found")

        tokens = (await session.execute(
            select(NarrativeToken)
            .where(NarrativeToken.narrative.contains(name))
            .order_by(NarrativeToken.price_change_pct.desc())
        )).scalars().all()

    return {
        "name": narrative.name,
        "token_count": narrative.token_count,
        "total_volume": narrative.total_volume,
        "total_mcap": narrative.total_mcap,
        "avg_mcap": narrative.avg_mcap,
        "avg_gain_pct": narrative.avg_gain_pct,
        "lifecycle": narrative.lifecycle,
        "tokens": [
            {
                "address": t.address,
                "name": t.name,
                "symbol": t.symbol,
                "mcap": t.mcap,
                "mcap_ath": t.mcap_ath,
                "price_change_pct": t.price_change_pct,
                "volume_24h": t.volume_24h,
                "liquidity_usd": t.liquidity_usd,
                "is_original": t.is_original,
                "parent_address": t.parent_address,
                "pair_address": t.pair_address,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tokens
        ],
    }
