# Narrative Tracker — Design Spec

## Purpose

Help Solana token devs figure out **what to launch** by showing which narratives are trending on-chain and which tokens are exploding right now. Part of the Candle Launch Terminal alongside Sol Outlook (when to launch) and Launch Monitor (what to expect).

Two planned sections:
- **On-chain Trends** (this spec) — what's actually pumping right now
- **CT Trends** (future) — what crypto Twitter is buzzing about, using LunarCrush or similar

## Architecture

### Data Pipeline

Scheduled job runs every 20 minutes:

1. **Scan** — fetch trending/top-gaining Solana tokens from DexScreener API. Collect ~50-100 tokens per scan with name, symbol, mcap, price change %, volume, age, pair address.

2. **Filter duplicates** — exact name match + same socials (or no socials) = duplicate. The older token is the original. Duplicates are flagged as forks but kept for signal ("3 copies launched today" = hot narrative).

3. **Filter scams** — RugCheck API for danger-level risks. Minimum liquidity and transaction thresholds. Score > 500 = excluded.

4. **Classify** — batch the filtered token names/symbols into a single Groq API call. Model: `llama-3.1-8b-instant`. Prompt asks Groq to categorize each token into a narrative (AI, Pets, Political, Gaming, Utility, Food, Celebrity, Meme, DeFi, Other). Returns structured JSON.

5. **Aggregate** — group tokens by narrative. Compute per-narrative stats: token count, total volume, average % gain, top performer.

6. **Lifecycle** — compute lifecycle stage per narrative:
   - **Emerging**: <5 tokens, volume growing
   - **Trending**: 5+ tokens, strong average gains
   - **Saturated**: many tokens but average gains declining
   - **Fading**: volume and launches dropping off

### Cost

Groq free tier: 14,400 requests/day, ~6,000 tokens/min for 8B model. We use ~72 requests/day with ~800 tokens each. Well within free limits.

### Fallback

If Groq is down or rate-limited, skip classification for that cycle and keep previous narrative assignments. No hard dependency on LLM availability.

## Backend Structure

```
app/narrative/
  scanner.py      — fetch trending tokens from DexScreener
  classifier.py   — Groq LLM narrative classification
  filters.py      — duplicate detection + scam filtering (RugCheck)
  models.py       — NarrativeToken, Narrative DB models

app/routers/
  narrative.py    — API endpoints
```

### Models

**NarrativeToken**
- `address` (PK) — token mint address
- `name` — token name
- `symbol` — token symbol
- `pair_address` — DexScreener pair
- `narrative` — classified narrative category
- `mcap` — current market cap
- `price_change_pct` — % change (from DexScreener, e.g. 24h)
- `volume_24h` — 24h trading volume
- `liquidity_usd` — pool liquidity
- `is_original` — True if original, False if fork/copy
- `parent_address` — address of the original token (if fork)
- `rugcheck_score` — from RugCheck API
- `created_at` — token creation time
- `first_seen` — when we first scanned it
- `last_seen` — last scan that included it

**Narrative**
- `id` (PK, autoincrement)
- `name` — narrative category name (AI, Pets, etc.)
- `token_count` — number of active tokens
- `total_volume` — combined 24h volume
- `avg_gain_pct` — average % gain across tokens
- `top_token_address` — best performer in this narrative
- `lifecycle` — emerging / trending / saturated / fading
- `last_updated` — timestamp

### API Endpoints

- `GET /api/narrative/overview` — all narratives ranked by momentum + top 10 runners by % gain from launch
- `GET /api/narrative/{name}` — detail view for one narrative with all its tokens

### Scheduled Job

Registered in `app/main.py` with APScheduler, same pattern as launch monitor jobs. Runs every 20 minutes (1200 seconds).

## Frontend

New page at `/narrative`, added to navigation alongside Sol Outlook and Launch Monitor.

### Narratives Panel

Cards ranked by momentum, each showing:
- Narrative name
- Lifecycle badge (Emerging / Trending / Saturated / Fading) with color coding
- Token count, total volume, average % gain
- Top token as quick reference
- Click to expand: shows all tokens in the narrative

### Top Runners Panel

Top 10 tokens by % gain from launch in the last 24h:
- Token name, symbol, narrative tag
- % gain from launch price
- Current mcap
- Age since launch
- DexScreener link
- Original vs fork flag

### Visual Style

Same terminal theme as existing pages — dark background, accent colors, cards with status dots and bars.

## Config

```python
# app/config.py
groq_api_key: str = ""  # Already added

# New intervals
fetch_interval_narrative: int = 1200  # 20 minutes
```

## Dependencies

- `groq` Python package (or raw httpx calls to Groq API)
- DexScreener API (already used)
- RugCheck API (already used)
- No new frontend dependencies

## Out of Scope

- CT Trends (Twitter/social signal) — deferred, will use LunarCrush later
- Historical narrative tracking over days/weeks — can add later
- Alerts/notifications when a new narrative emerges
