"""Groq LLM narrative classifier for trending tokens."""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """Categorize each Solana memecoin into its narrative themes. A token can belong to MULTIPLE narratives.

Return ONLY JSON: [{"token":"name","narratives":["category1","category2"]}]

Examples:
- "Pixel Trump" -> ["Art/Pixel", "Political"]
- "Vaping Penguin" -> ["Animals", "Absurdist"]
- "DogAI" -> ["Animals", "AI"]
- "Buttcoin" -> ["Finance Parody"]

Common narratives: Animals, AI, Political, Art/Pixel, Culture, Celebrity, Absurdist, Finance Parody, Adult/NSFW, Gaming, Anime, Food

Rules:
- If a token fits multiple categories, list ALL of them (max 3)
- If the name mentions ANY animal (dog, cat, wolf, penguin, frog, inu, pup) it MUST include "Animals"
- If political (Trump, government, bank, nation) it MUST include "Political"
- You CAN invent new categories if you spot a clear theme
- Do NOT use "Other" or "Meme" — dig deeper"""


async def classify_narratives(
    tokens: list[dict],
    api_key: str,
    http_client: httpx.AsyncClient,
) -> dict[str, list[str]]:
    """Classify tokens into narratives using Groq LLM.

    Returns dict mapping token address -> list of narrative categories.
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

    # Map by name, symbol, and "name (symbol)" since Groq may return any format
    lookup: dict[str, str] = {}
    for t in tokens:
        lookup[t["name"]] = t["address"]
        lookup[t["symbol"]] = t["address"]
        lookup[f"{t['name']} ({t['symbol']})"] = t["address"]

    result: dict[str, list[str]] = {}
    for item in classifications:
        token_ref = item.get("token", "")
        narratives = item.get("narratives") or [item.get("narrative", "")]
        if isinstance(narratives, str):
            narratives = [narratives]
        narratives = [n for n in narratives if n and n not in ("Other", "Meme")]
        if not narratives:
            narratives = ["Absurdist"]
        addr = lookup.get(token_ref)
        if addr:
            result[addr] = narratives

    return result
