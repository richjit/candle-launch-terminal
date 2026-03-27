# backend/app/fetchers/google_trends.py
import asyncio
import logging
import random
from app.fetchers.base import BaseFetcher

logger = logging.getLogger(__name__)

KEYWORDS = ["solana", "ethereum", "bitcoin"]


class GoogleTrendsFetcher(BaseFetcher):
    @property
    def source_name(self) -> str:
        return "google_trends"

    async def fetch_data(self) -> dict:
        # Run pytrends in a thread to avoid blocking the event loop
        import concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, self._fetch_sync)
        return result

    def _fetch_sync(self) -> dict:
        import time
        from pytrends.request import TrendReq

        # Random delay to avoid rate limiting
        time.sleep(random.uniform(1, 3))

        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pytrends.build_payload(KEYWORDS, timeframe="now 7-d")
        df = pytrends.interest_over_time()

        if df.empty:
            logger.warning("Google Trends returned empty data")
            return {kw: 0 for kw in KEYWORDS}

        # Get the latest values
        latest = df.iloc[-1]
        return {kw: int(latest.get(kw, 0)) for kw in KEYWORDS}

    def parse_response(self, data: dict) -> list[dict]:
        solana_val = data.get("solana", 0)
        return [{
            "metric_name": "google_trends",
            "value": float(solana_val),
            "metadata": data,
        }]
