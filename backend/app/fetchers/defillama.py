# backend/app/fetchers/defillama.py
from app.fetchers.base import BaseFetcher


class DefiLlamaFetcher(BaseFetcher):
    BASE_URL = "https://api.llama.fi"
    DEX_URL = "https://api.llama.fi/overview/dexs/solana"
    STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoinchains"

    @property
    def source_name(self) -> str:
        return "defillama"

    async def fetch_data(self) -> dict:
        tvl_resp = await self.http.get(
            f"{self.BASE_URL}/v2/historicalChainTvl/Solana", timeout=15.0
        )
        tvl_resp.raise_for_status()

        dex_resp = await self.http.get(self.DEX_URL, timeout=15.0)
        dex_resp.raise_for_status()

        chains_resp = await self.http.get(f"{self.BASE_URL}/v2/chains", timeout=15.0)
        chains_resp.raise_for_status()

        stables_resp = await self.http.get(self.STABLECOINS_URL, timeout=15.0)
        stables_resp.raise_for_status()

        return {
            "tvl_history": tvl_resp.json(),
            "dex_volume": dex_resp.json(),
            "chains_tvl": chains_resp.json(),
            "stablecoins": stables_resp.json(),
        }

    def parse_response(self, data: dict) -> list[dict]:
        metrics = []

        # Solana TVL (latest)
        tvl_history = data.get("tvl_history") or []
        if tvl_history:
            latest_tvl = tvl_history[-1].get("tvl", 0)
            history = [{"timestamp": h["date"], "value": h["tvl"]} for h in tvl_history[-30:]]
            metrics.append({
                "metric_name": "solana_tvl",
                "value": latest_tvl,
                "metadata": {"history": history},
            })

        # DEX volume
        dex_data = data.get("dex_volume", {})
        vol_24h = dex_data.get("total24h", 0)
        metrics.append({
            "metric_name": "dex_volume_24h",
            "value": float(vol_24h or 0),
            "metadata": None,
        })

        # Cross-chain TVL comparison
        chains = data.get("chains_tvl") or []
        chain_map = {}
        for c in chains:
            name = c.get("name", "")
            if name in ("Ethereum", "Solana", "Base", "Arbitrum", "BSC"):
                chain_map[name] = float(c.get("tvl", 0))
        metrics.append({
            "metric_name": "chains_tvl",
            "value": chain_map.get("Solana", 0),
            "metadata": {"chains": chain_map},
        })

        # Stablecoin distribution by chain (proxy for capital flows)
        stables = data.get("stablecoins") or {}
        stable_chains = stables.get("chains") if isinstance(stables, dict) else stables
        if isinstance(stable_chains, list):
            stable_map = {}
            for c in stable_chains:
                name = c.get("name", "")
                if name in ("Ethereum", "Solana", "Base", "Arbitrum", "BSC"):
                    pegged = c.get("totalCirculatingUSD", {})
                    stable_map[name] = float(pegged.get("peggedUSD", 0) if isinstance(pegged, dict) else 0)
            metrics.append({
                "metric_name": "stablecoin_flows",
                "value": stable_map.get("Solana", 0),
                "metadata": stable_map,
            })

        return metrics
