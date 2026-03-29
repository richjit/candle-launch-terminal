import pytest
import httpx
import respx
from app.narrative.filters import filter_duplicates, filter_scams


def test_filter_duplicates_exact_name():
    tokens = [
        {"address": "a1", "name": "DogAI", "symbol": "DOGAI", "mcap": 100000, "created_at": "2026-03-28T10:00:00"},
        {"address": "a2", "name": "DogAI", "symbol": "DOGAI2", "mcap": 50000, "created_at": "2026-03-28T12:00:00"},
        {"address": "a3", "name": "CatCoin", "symbol": "CAT", "mcap": 80000, "created_at": "2026-03-28T11:00:00"},
    ]
    result = filter_duplicates(tokens)
    originals = [t for t in result if t["is_original"]]
    forks = [t for t in result if not t["is_original"]]
    assert len(originals) == 2
    assert len(forks) == 1
    assert forks[0]["parent_address"] == "a1"


def test_filter_duplicates_no_duplicates():
    tokens = [
        {"address": "a1", "name": "Alpha", "symbol": "A", "mcap": 100, "created_at": "2026-03-28T10:00:00"},
        {"address": "a2", "name": "Beta", "symbol": "B", "mcap": 200, "created_at": "2026-03-28T10:00:00"},
    ]
    result = filter_duplicates(tokens)
    assert all(t["is_original"] for t in result)


@pytest.mark.asyncio
@respx.mock
async def test_filter_scams_removes_dangerous():
    tokens = [
        {"address": "good_token", "name": "Good", "symbol": "G", "liquidity_usd": 5000},
        {"address": "bad_token", "name": "Scam", "symbol": "S", "liquidity_usd": 5000},
    ]
    respx.get("https://api.rugcheck.xyz/v1/tokens/good_token/report/summary").mock(
        return_value=httpx.Response(200, json={"risks": [], "score": 0, "score_normalised": 0})
    )
    respx.get("https://api.rugcheck.xyz/v1/tokens/bad_token/report/summary").mock(
        return_value=httpx.Response(200, json={
            "risks": [{"level": "danger", "score": 5000, "name": "Single holder"}],
            "score": 5000, "score_normalised": 80
        })
    )
    async with httpx.AsyncClient() as client:
        result = await filter_scams(tokens, client)
    assert len(result) == 1
    assert result[0]["address"] == "good_token"
