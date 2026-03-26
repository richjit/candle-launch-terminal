# backend/app/fetchers/solana_rpc.py
import logging
from app.fetchers.base import BaseFetcher
from app.cache import MemoryCache
import httpx

logger = logging.getLogger(__name__)

# Stablecoin mint addresses on Solana
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


class SolanaRpcFetcher(BaseFetcher):
    def __init__(self, cache: MemoryCache, http_client: httpx.AsyncClient, rpc_url: str, db_engine=None):
        super().__init__(cache=cache, http_client=http_client, db_engine=db_engine)
        self.rpc_url = rpc_url

    @property
    def source_name(self) -> str:
        return "solana_rpc"

    async def _rpc_call(self, method: str, params: list | None = None) -> dict:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        resp = await self.http.post(self.rpc_url, json=payload, timeout=15.0)
        resp.raise_for_status()
        return resp.json()

    async def fetch_data(self) -> dict:
        tps_data = await self._rpc_call("getRecentPerformanceSamples", [10])
        fees_data = await self._rpc_call("getRecentPrioritizationFees")
        usdc_supply = await self._rpc_call("getTokenSupply", [USDC_MINT])
        usdt_supply = await self._rpc_call("getTokenSupply", [USDT_MINT])
        return {
            "tps": tps_data,
            "priority_fees": fees_data,
            "usdc_supply": usdc_supply,
            "usdt_supply": usdt_supply,
        }

    def parse_response(self, data: dict) -> list[dict]:
        metrics = []
        metrics.extend(self._parse_tps(data["tps"]))
        metrics.extend(self._parse_priority_fees(data["priority_fees"]))

        usdc = self._parse_token_supply(data["usdc_supply"])
        usdt = self._parse_token_supply(data["usdt_supply"])
        metrics.append({
            "metric_name": "stablecoin_supply",
            "value": usdc + usdt,
            "metadata": {"usdc": usdc, "usdt": usdt},
        })
        return metrics

    def _parse_tps(self, data: dict) -> list[dict]:
        samples = data.get("result") or []
        if not samples:
            return []
        avg_tps = sum(
            s["numTransactions"] / max(s["samplePeriodSecs"], 1) for s in samples
        ) / len(samples)
        return [{"metric_name": "tps", "value": avg_tps, "metadata": {"sample_count": len(samples)}}]

    def _parse_priority_fees(self, data: dict) -> list[dict]:
        fees = data.get("result") or []
        if not fees:
            return []
        avg_fee = sum(f["prioritizationFee"] for f in fees) / len(fees)
        return [{"metric_name": "priority_fees", "value": avg_fee, "metadata": {"sample_count": len(fees)}}]

    def _parse_token_supply(self, data: dict) -> float:
        try:
            return float(data["result"]["value"]["uiAmount"] or 0)
        except (KeyError, TypeError):
            return 0.0
