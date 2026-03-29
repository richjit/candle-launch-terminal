# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./candle.db"

    # API Keys (all optional)
    helius_api_key: str = ""
    coingecko_api_key: str = ""
    dune_api_key: str = ""
    github_token: str = ""

    # Solana RPC
    @property
    def solana_rpc_url(self) -> str:
        if self.helius_api_key:
            return f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"
        return "https://api.mainnet-beta.solana.com"

    # Fetch intervals (seconds)
    fetch_interval_rpc: int = 120
    fetch_interval_dexscreener: int = 60
    fetch_interval_defillama: int = 300
    fetch_interval_coingecko: int = 300
    fetch_interval_fear_greed: int = 3600
    fetch_interval_google_trends: int = 3600
    fetch_interval_github: int = 21600

    # Launch monitor intervals (seconds)
    fetch_interval_launch_discovery: int = 120   # 2 min
    fetch_interval_launch_enrichment: int = 120  # 2 min

    # Stale data thresholds (seconds)
    stale_threshold_rpc: int = 300
    stale_threshold_dexscreener: int = 300
    stale_threshold_defillama: int = 1800
    stale_threshold_coingecko: int = 1800
    stale_threshold_fear_greed: int = 7200
    stale_threshold_google_trends: int = 21600

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    """Factory function for settings. Allows test overrides."""
    return Settings()
