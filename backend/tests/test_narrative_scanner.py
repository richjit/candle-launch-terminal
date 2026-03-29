import pytest
import httpx
import respx
from app.narrative.scanner import scan_trending_tokens

MOCK_BOOSTS = [
    {"chainId": "solana", "tokenAddress": "token1pump"},
    {"chainId": "solana", "tokenAddress": "token2abc"},
]

MOCK_PAIRS = [
    {
        "chainId": "solana",
        "pairAddress": "pair1",
        "baseToken": {"address": "token1pump", "name": "DogAI", "symbol": "DOGAI"},
        "marketCap": 50000,
        "volume": {"h24": 100000},
        "liquidity": {"usd": 10000},
        "priceChange": {"h24": 250.0},
        "pairCreatedAt": 1774300000000,
    },
    {
        "chainId": "solana",
        "pairAddress": "pair2",
        "baseToken": {"address": "token2abc", "name": "CatCoin", "symbol": "CAT"},
        "marketCap": 200000,
        "volume": {"h24": 500000},
        "liquidity": {"usd": 50000},
        "priceChange": {"h24": 180.0},
        "pairCreatedAt": 1774300000000,
    },
]


@pytest.mark.asyncio
@respx.mock
async def test_scan_trending_tokens():
    respx.get("https://api.dexscreener.com/token-boosts/top/v1").mock(
        return_value=httpx.Response(200, json=MOCK_BOOSTS)
    )
    respx.get(url__startswith="https://api.dexscreener.com/tokens/v1/solana/").mock(
        return_value=httpx.Response(200, json=MOCK_PAIRS)
    )
    async with httpx.AsyncClient() as client:
        tokens = await scan_trending_tokens(client)
    assert len(tokens) == 2
    assert tokens[0]["name"] == "DogAI"
    assert tokens[0]["address"] == "token1pump"


@pytest.mark.asyncio
@respx.mock
async def test_scan_filters_non_solana():
    respx.get("https://api.dexscreener.com/token-boosts/top/v1").mock(
        return_value=httpx.Response(200, json=[
            {"chainId": "ethereum", "tokenAddress": "x"},
        ])
    )
    async with httpx.AsyncClient() as client:
        tokens = await scan_trending_tokens(client)
    assert len(tokens) == 0
