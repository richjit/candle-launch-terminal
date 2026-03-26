# backend/app/scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def register_fetcher_job(fetcher, interval_seconds: int):
    """Register a fetcher to run on a fixed interval."""
    job_id = f"fetch_{fetcher.source_name}"
    scheduler.add_job(
        fetcher.run,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id=job_id,
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Registered job {job_id} every {interval_seconds}s")
