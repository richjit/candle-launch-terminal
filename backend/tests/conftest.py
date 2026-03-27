# backend/tests/conftest.py
import pytest
from app.config import Settings

@pytest.fixture
def test_settings():
    return Settings(
        database_url="sqlite+aiosqlite:///./test_candle.db",
        helius_api_key="",
    )
