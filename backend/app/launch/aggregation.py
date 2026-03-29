"""Daily aggregation of launch token data and old token cleanup."""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from sqlalchemy import select, delete

from app.database import get_session, HistoricalData
from app.launch.models import LaunchToken, LaunchDailyStats

logger = logging.getLogger(__name__)

RETENTION_DAYS = 90


async def aggregate_launch_stats(engine) -> int:
    """Compute daily stats from launch_tokens and upsert into launch_daily_stats.

    Returns number of rows upserted.
    """
    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchToken).where(LaunchToken.checkpoint_complete == True)  # noqa: E712
        )
        tokens = result.scalars().all()

    if not tokens:
        return 0

    # Group by (date, launchpad)
    groups: dict[tuple[date, str], list[LaunchToken]] = defaultdict(list)
    all_by_date: dict[date, list[LaunchToken]] = defaultdict(list)

    for token in tokens:
        # Handle naive datetimes from SQLite
        created_at = token.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        d = created_at.date()
        groups[(d, token.launchpad)].append(token)
        all_by_date[d].append(token)

    # Also add "all" aggregate per date
    for d, toks in all_by_date.items():
        groups[(d, "all")] = toks

    # Load pump.fun daily creates for migration rate calculation
    pumpfun_creates_by_date: dict[date, float] = {}
    async with get_session(engine) as session:
        result = await session.execute(
            select(HistoricalData).where(HistoricalData.source == "pumpfun_creates")
        )
        for row in result.scalars().all():
            pumpfun_creates_by_date[row.date] = row.value

    count = 0
    async with get_session(engine) as session:
        for (d, launchpad), toks in groups.items():
            denominator = pumpfun_creates_by_date.get(d)
            stats = _compute_stats(toks, denominator)

            # Upsert
            result = await session.execute(
                select(LaunchDailyStats).where(
                    LaunchDailyStats.date == d,
                    LaunchDailyStats.launchpad == launchpad,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                for key, value in stats.items():
                    setattr(existing, key, value)
            else:
                row = LaunchDailyStats(date=d, launchpad=launchpad, **stats)
                session.add(row)
            count += 1

        await session.commit()

    if count:
        logger.info(f"Aggregated {count} daily stat row(s)")
    return count


def _compute_stats(tokens: list[LaunchToken], pumpfun_creates: float | None = None) -> dict:
    """Compute aggregate stats for a group of tokens.

    Args:
        tokens: Tracked tokens for the group.
        pumpfun_creates: Total pump.fun token creates that day (denominator for migration rate).
    """
    n = len(tokens)
    peaks_1h = [t.mcap_peak_1h for t in tokens if t.mcap_peak_1h is not None]
    peaks_24h = [t.mcap_peak_24h for t in tokens if t.mcap_peak_24h is not None]
    peaks_7d = [t.mcap_peak_7d for t in tokens if t.mcap_peak_7d is not None]
    times_to_peak = [t.time_to_peak_minutes for t in tokens if t.time_to_peak_minutes is not None]

    alive_1h = sum(1 for t in tokens if t.volume_1h is not None and t.volume_1h >= 100)
    alive_24h = sum(1 for t in tokens if t.volume_24h is not None and t.volume_24h >= 100)
    alive_7d = sum(1 for t in tokens if t.is_alive)
    with_1h = sum(1 for t in tokens if t.volume_1h is not None)
    with_24h = sum(1 for t in tokens if t.volume_24h is not None)

    buy_sell_ratios = []
    for t in tokens:
        if t.buys_1h is not None and t.sells_1h and t.sells_1h > 0:
            buy_sell_ratios.append(t.buys_1h / t.sells_1h)

    volumes = [t.volume_1h for t in tokens if t.volume_1h is not None]

    # Migration rate: tokens that migrated to DEX / total pump.fun creates
    tokens_created = int(pumpfun_creates) if pumpfun_creates else n
    migration_rate = (n / pumpfun_creates * 100) if pumpfun_creates and pumpfun_creates > 0 else 0.0

    return {
        "tokens_created": tokens_created,
        "tokens_migrated": n,
        "migration_rate": migration_rate,
        "median_peak_mcap_1h": median(peaks_1h) if peaks_1h else None,
        "median_peak_mcap_24h": median(peaks_24h) if peaks_24h else None,
        "median_peak_mcap_7d": median(peaks_7d) if peaks_7d else None,
        "median_time_to_peak": median(times_to_peak) if times_to_peak else None,
        "survival_rate_1h": (alive_1h / with_1h * 100) if with_1h else None,
        "survival_rate_24h": (alive_24h / with_24h * 100) if with_24h else None,
        "survival_rate_7d": (alive_7d / n * 100) if n else None,
        "avg_buy_sell_ratio_1h": (sum(buy_sell_ratios) / len(buy_sell_ratios)) if buy_sell_ratios else None,
        "total_launches": n,
        "total_volume": sum(volumes) if volumes else None,
    }


async def cleanup_old_tokens(engine) -> int:
    """Delete launch_tokens rows that are complete, older than RETENTION_DAYS,
    and whose data has been aggregated into launch_daily_stats.

    Returns number of rows deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

    async with get_session(engine) as session:
        result = await session.execute(
            select(LaunchToken).where(
                LaunchToken.checkpoint_complete == True,  # noqa: E712
                LaunchToken.created_at < cutoff,
            )
        )
        candidates = result.scalars().all()
        if not candidates:
            return 0

        # Only delete tokens whose date has a corresponding aggregation row
        dates_to_check = set()
        for t in candidates:
            created_at = t.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            dates_to_check.add(created_at.date())

        agg_result = await session.execute(
            select(LaunchDailyStats.date).where(
                LaunchDailyStats.date.in_(dates_to_check),
                LaunchDailyStats.launchpad == "all",
            )
        )
        aggregated_dates = set(agg_result.scalars().all())

        to_delete = []
        for t in candidates:
            created_at = t.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at.date() in aggregated_dates:
                to_delete.append(t)

        for token in to_delete:
            await session.delete(token)

        deleted = len(to_delete)
        if deleted:
            await session.commit()
            logger.info(f"Cleaned up {deleted} old launch token(s)")
    return deleted
