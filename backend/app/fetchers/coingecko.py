# backend/app/fetchers/coingecko.py
from app.fetchers.base import BaseFetcher
from app.cache import MemoryCache
import httpx


class CoinGeckoFetcher(BaseFetcher):
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, cache: MemoryCache, http_client: httpx.AsyncClient, api_key: str, db_engine=None):
        super().__init__(cache=cache, http_client=http_client, db_engine=db_engine)
        self.api_key = api_key

    @property
    def source_name(self) -> str:
        return "coingecko"

    async def fetch_data(self) -> dict:
        headers = {}
        if self.api_key:
            headers["x-cg-demo-api-key"] = self.api_key
        resp = await self.http.get(
            f"{self.BASE_URL}/simple/price",
            params={
                "ids": "solana",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_7d_change": "true",
                "include_30d_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true",
            },
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()

    def parse_response(self, data: dict) -> list[dict]:
        sol = data.get("solana", {})
        return [
            {
                "metric_name": "sol_price",
                "value": float(sol.get("usd", 0)),
                "metadata": {
                    "change_24h": float(sol.get("usd_24h_change", 0)),
                    "change_7d": float(sol.get("usd_7d_change", 0)),
                    "change_30d": float(sol.get("usd_30d_change", 0)),
                    "volume_24h": float(sol.get("usd_24h_vol", 0)),
                    "market_cap": float(sol.get("usd_market_cap", 0)),
                },
            }
        ]
