# backend/app/fetchers/dexscreener.py
from app.fetchers.base import BaseFetcher


class DexScreenerFetcher(BaseFetcher):
    BASE_URL = "https://api.dexscreener.com/latest/dex"

    @property
    def source_name(self) -> str:
        return "dexscreener"

    async def fetch_data(self) -> dict:
        resp = await self.http.get(
            f"{self.BASE_URL}/tokens/So11111111111111111111111111111111111111112",
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()

    def parse_response(self, data: dict) -> list[dict]:
        pairs = data.get("pairs") or []
        parsed_pairs = []
        for p in pairs[:20]:  # Top 20 pairs
            parsed_pairs.append({
                "symbol": p.get("baseToken", {}).get("symbol", ""),
                "name": p.get("baseToken", {}).get("name", ""),
                "price_usd": float(p.get("priceUsd") or 0),
                "volume_24h": float(p.get("volume", {}).get("h24") or 0),
                "liquidity_usd": float(p.get("liquidity", {}).get("usd") or 0),
                "price_change_24h": float(p.get("priceChange", {}).get("h24") or 0),
                "fdv": float(p.get("fdv") or 0),
                "pair_address": p.get("pairAddress", ""),
            })

        total_volume = sum(p["volume_24h"] for p in parsed_pairs)

        return [
            {
                "metric_name": "top_pairs",
                "value": total_volume,
                "metadata": {"pairs": parsed_pairs},
            },
            {
                "metric_name": "sol_total_volume_24h",
                "value": total_volume,
                "metadata": None,
            },
        ]
