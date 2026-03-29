"""Groq LLM narrative classifier for trending tokens."""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You categorize Solana meme tokens into market narratives.

Return ONLY a JSON array: [{"token": "name", "narrative": "category"}]

Categories: AI, Pets, Political, Gaming, Utility, Food, Celebrity, Meme, DeFi, Other

Rules:
- Use the token name and symbol to determine the best category
- If unsure, use "Meme" as the default
- Keep category names exactly as listed above
- No explanation, just the JSON array"""


async def classify_narratives(
    tokens: list[dict],
    api_key: str,
    http_client: httpx.AsyncClient,
) -> dict[str, str]:
    """Classify tokens into narratives using Groq LLM.

    Returns dict mapping token address -> narrative category.
    """
    if not tokens or not api_key:
        return {}

    token_list = ", ".join(f"{t['name']} ({t['symbol']})" for t in tokens)

    try:
        resp = await http_client.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Categorize: {token_list}"},
                ],
                "temperature": 0,
                "max_tokens": 1024,
            },
            timeout=30.0,
        )

        if resp.status_code != 200:
            logger.warning(f"Groq API error: {resp.status_code}")
            return {}

        content = resp.json()["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        classifications = json.loads(content)
    except Exception as e:
        logger.warning(f"Groq classification failed: {e}")
        return {}

    name_to_addr = {t["name"]: t["address"] for t in tokens}
    result = {}
    for item in classifications:
        name = item.get("token", "")
        narrative = item.get("narrative", "Other")
        if name in name_to_addr:
            result[name_to_addr[name]] = narrative

    return result
