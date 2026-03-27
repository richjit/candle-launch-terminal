# backend/tests/test_config.py
import pytest
from app.config import Settings

ENV_VARS_TO_CLEAR = [
    "DATABASE_URL", "HELIUS_API_KEY", "COINGECKO_API_KEY", "GITHUB_TOKEN",
    "FETCH_INTERVAL_RPC", "FETCH_INTERVAL_DEXSCREENER", "FETCH_INTERVAL_DEFILLAMA",
    "FETCH_INTERVAL_COINGECKO", "FETCH_INTERVAL_FEAR_GREED", "FETCH_INTERVAL_GOOGLE_TRENDS",
    "FETCH_INTERVAL_GITHUB",
    "STALE_THRESHOLD_RPC", "STALE_THRESHOLD_DEXSCREENER", "STALE_THRESHOLD_DEFILLAMA",
    "STALE_THRESHOLD_COINGECKO", "STALE_THRESHOLD_FEAR_GREED", "STALE_THRESHOLD_GOOGLE_TRENDS",
]

def test_settings_defaults(monkeypatch):
    for var in ENV_VARS_TO_CLEAR:
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite+aiosqlite:///./candle.db"
    assert settings.solana_rpc_url == "https://api.mainnet-beta.solana.com"
    assert settings.fetch_interval_rpc == 120
    assert settings.fetch_interval_dexscreener == 60
    assert settings.fetch_interval_defillama == 300
    assert settings.fetch_interval_coingecko == 300
    assert settings.fetch_interval_fear_greed == 3600
    assert settings.fetch_interval_google_trends == 3600
    assert settings.fetch_interval_github == 21600
    assert settings.stale_threshold_rpc == 300
    assert settings.stale_threshold_dexscreener == 300
    assert settings.stale_threshold_defillama == 1800
    assert settings.stale_threshold_coingecko == 1800
    assert settings.stale_threshold_fear_greed == 7200
    assert settings.stale_threshold_google_trends == 21600

def test_settings_helius_rpc_url():
    settings = Settings(helius_api_key="test-key")
    assert settings.solana_rpc_url == "https://mainnet.helius-rpc.com/?api-key=test-key"
