"""Groq LLM narrative classifier for trending tokens."""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """Categorize each Solana memecoin into its narrative theme. Return ONLY JSON: [{"token":"name","narrative":"category"}]

Pick the BEST fit. If the name mentions ANY animal (dog, cat, wolf, penguin, frog, inu, pup) → Animals. If political (Trump, bank, nation, government) → Political. Use your best judgment.

Common narratives: Animals, AI, Political, Art/Pixel, Culture, Celebrity, Absurdist, Finance Parody, Adult/NSFW, Gaming, Anime, Food

You CAN invent new categories if you spot a clear theme. Do NOT use "Other" or "Meme" — every token has a theme, find it."""


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

    # Map by both name and symbol since Groq may return either
    name_to_addr = {t["name"]: t["address"] for t in tokens}
    symbol_to_addr = {t["symbol"]: t["address"] for t in tokens}
    result = {}
    for item in classifications:
        token_ref = item.get("token", "")
        narrative = item.get("narrative", "")
        if not narrative or narrative in ("Other", "Meme"):
            narrative = "Absurdist"  # Fallback for unclassified
        addr = name_to_addr.get(token_ref) or symbol_to_addr.get(token_ref)
        if addr:
            result[addr] = narrative

    return result
