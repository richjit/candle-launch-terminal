# backend/app/fetchers/fear_greed.py
from app.fetchers.base import BaseFetcher


class FearGreedFetcher(BaseFetcher):
    URL = "https://api.alternative.me/fng/"

    @property
    def source_name(self) -> str:
        return "fear_greed"

    async def fetch_data(self) -> dict:
        resp = await self.http.get(self.URL, params={"limit": 1}, timeout=15.0)
        resp.raise_for_status()
        return resp.json()

    def parse_response(self, data: dict) -> list[dict]:
        entries = data.get("data") or []
        if not entries:
            return []
        entry = entries[0]
        return [{
            "metric_name": "fear_greed",
            "value": float(entry.get("value", 0)),
            "metadata": {"label": entry.get("value_classification", "Unknown")},
        }]
