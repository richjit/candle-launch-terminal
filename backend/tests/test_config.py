# backend/tests/test_config.py
from app.config import Settings

def test_settings_defaults():
    settings = Settings()
    assert settings.database_url == "sqlite+aiosqlite:///./candle.db"
    assert settings.solana_rpc_url == "https://api.mainnet-beta.solana.com"
    assert settings.fetch_interval_rpc == 120
    assert settings.fetch_interval_dexscreener == 60
    assert settings.fetch_interval_defillama == 300
    assert settings.fetch_interval_coingecko == 300
    assert settings.fetch_interval_fear_greed == 3600
    assert settings.fetch_interval_google_trends == 3600

def test_settings_helius_rpc_url():
    settings = Settings(helius_api_key="test-key")
    assert "test-key" in settings.solana_rpc_url
