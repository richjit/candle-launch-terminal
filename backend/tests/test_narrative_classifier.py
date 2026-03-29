import pytest
import httpx
import respx
from app.narrative.classifier import classify_narratives

MOCK_GROQ_RESPONSE = {
    "choices": [{
        "message": {
            "content": '[{"token": "DogAI", "narrative": "AI"}, {"token": "CatCoin", "narrative": "Pets"}]'
        }
    }]
}


@pytest.mark.asyncio
@respx.mock
async def test_classify_narratives():
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=MOCK_GROQ_RESPONSE)
    )
    tokens = [
        {"name": "DogAI", "symbol": "DOGAI", "address": "a1"},
        {"name": "CatCoin", "symbol": "CAT", "address": "a2"},
    ]
    async with httpx.AsyncClient() as client:
        result = await classify_narratives(tokens, "fake-api-key", client)
    assert result["a1"] == "AI"
    assert result["a2"] == "Pets"


@pytest.mark.asyncio
@respx.mock
async def test_classify_handles_groq_failure():
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(500)
    )
    tokens = [{"name": "Test", "symbol": "T", "address": "a1"}]
    async with httpx.AsyncClient() as client:
        result = await classify_narratives(tokens, "fake-key", client)
    assert result == {}
