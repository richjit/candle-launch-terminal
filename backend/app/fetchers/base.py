# backend/app/fetchers/base.py
import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx

from app.cache import MemoryCache
from app.resilience import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    """Base class for all data source fetchers.

    Subclasses implement `source_name`, `fetch_data`, and `parse_response`.
    The `run` method handles the full cycle: check circuit → fetch → parse → store.

    Note: Subclasses should NOT use @retry_with_backoff on fetch_data.
    Retries are handled here in run() to coordinate with the circuit breaker.
    """

    def __init__(self, cache: MemoryCache, http_client: httpx.AsyncClient, db_engine=None):
        self.cache = cache
        self.http = http_client
        self.db_engine = db_engine
        self.circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=300)
        self.last_fetch_at: datetime | None = None
        self.error_count: int = 0

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source."""

    @abstractmethod
    async def fetch_data(self) -> dict:
        """Fetch raw data from the external API. Returns parsed JSON."""

    @abstractmethod
    def parse_response(self, data: dict) -> list[dict]:
        """Parse raw API response into list of metric dicts.

        Each dict: {"metric_name": str, "value": float, "metadata": dict | None}
        """

    async def run(self) -> list[dict]:
        """Full fetch cycle: circuit check → retry fetch → parse → cache + DB."""
        try:
            self.circuit.check()
        except CircuitOpenError as e:
            logger.warning(f"[{self.source_name}] {e}")
            return []

        # Retry loop (coordinated with circuit breaker)
        last_err = None
        for attempt in range(3):
            try:
                raw_data = await self.fetch_data()
                metrics = self.parse_response(raw_data)
                now = datetime.now(timezone.utc)
                self.last_fetch_at = now
                self.error_count = 0
                self.circuit.record_success()

                # Cache each metric
                for m in metrics:
                    cache_key = f"{self.source_name}:{m['metric_name']}"
                    self.cache.set(cache_key, {**m, "fetched_at": now.isoformat()}, ttl=600)

                # Persist to DB for historical analysis
                if self.db_engine:
                    await self._persist_metrics(metrics, now)

                logger.info(f"[{self.source_name}] Fetched {len(metrics)} metrics")
                return metrics

            except Exception as e:
                last_err = e
                if attempt < 2:
                    delay = (1.0 * (4 ** attempt)) + random.uniform(0, 1)
                    logger.warning(f"[{self.source_name}] Attempt {attempt+1} failed: {e}. Retry in {delay:.1f}s")
                    await asyncio.sleep(delay)

        # All retries exhausted
        self.error_count += 1
        self.circuit.record_failure()
        logger.error(f"[{self.source_name}] Fetch failed after 3 attempts: {last_err}")
        return []

    async def _persist_metrics(self, metrics: list[dict], fetched_at: datetime):
        """Write metrics to the database for historical analysis."""
        try:
            from app.database import get_session, MetricData
            async with get_session(self.db_engine) as session:
                for m in metrics:
                    if "metric_name" not in m or "value" not in m:
                        logger.warning(f"[{self.source_name}] Skipping malformed metric: {m}")
                        continue
                    row = MetricData(
                        source=self.source_name,
                        metric_name=m["metric_name"],
                        value=m["value"],
                        metadata_json=json.dumps(m.get("metadata")) if m.get("metadata") else None,
                        fetched_at=fetched_at,
                    )
                    session.add(row)
                await session.commit()
        except Exception as e:
            logger.error(f"[{self.source_name}] DB persist failed: {e}")

    def status(self) -> dict:
        """Return current fetcher health status."""
        return {
            "source": self.source_name,
            "last_fetch_at": self.last_fetch_at.isoformat() if self.last_fetch_at else None,
            "error_count": self.error_count,
            "circuit_open": self.circuit.is_open,
        }
