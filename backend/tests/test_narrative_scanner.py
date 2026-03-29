import pytest
import httpx
import respx
from app.narrative.scanner import scan_trending_tokens

MOCK_RESPONSE = [
    {
        "chainId": "solana",
        "dexId": "pumpswap",
        "pairAddress": "pair1",
        "baseToken": {"address": "token1pump", "name": "DogAI", "symbol": "DOGAI"},
        "priceUsd": "0.001",
        "marketCap": 50000,
        "volume": {"h24": 100000},
        "liquidity": {"usd": 10000},
        "priceChange": {"h24": 250.0},
        "pairCreatedAt": 1774300000000,
    },
    {
        "chainId": "solana",
        "dexId": "raydium",
        "pairAddress": "pair2",
        "baseToken": {"address": "token2abc", "name": "CatCoin", "symbol": "CAT"},
        "priceUsd": "0.05",
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
        return_value=httpx.Response(200, json=MOCK_RESPONSE)
    )
    async with httpx.AsyncClient() as client:
        tokens = await scan_trending_tokens(client)
    assert len(tokens) == 2
    assert tokens[0]["name"] == "DogAI"
    assert tokens[0]["address"] == "token1pump"


@pytest.mark.asyncio
@respx.mock
async def test_scan_filters_non_solana():
    data = [{"chainId": "ethereum", "baseToken": {"address": "x", "name": "Y", "symbol": "Y"}}]
    respx.get("https://api.dexscreener.com/token-boosts/top/v1").mock(
        return_value=httpx.Response(200, json=data)
    )
    async with httpx.AsyncClient() as client:
        tokens = await scan_trending_tokens(client)
    assert len(tokens) == 0
