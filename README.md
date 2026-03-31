# Candle Launch Terminal

Real-time Solana launch intelligence for token developers — all on a single dashboard.

**Is it a good time to launch?** Health score, SOL chart, and market conditions give you the answer at a glance.

**What should I launch?** AI-classified trending narratives show which themes have momentum right now.

## Features

- **Health Score** — 0-100 gauge based on TVL, Fear & Greed Index, and Chain Fee Revenue
- **SOL Price Chart** — Interactive candlestick chart with health score overlay
- **Market Conditions** — Green/red checklist: launches, graduation rate, survival, buy/sell ratio, DEX volume
- **Launch Performance** — Peak market cap tiers for graduated tokens (Best, Top 10%, Bonded, All)
- **Launchpad Activity** — Per-platform launch counts from Dune (pump.fun, LetsBonk, Bags, Moonshot, etc.)
- **Trending Narratives** — AI-classified token themes with lifecycle stages (Emerging, Trending, Saturated, Fading)
- **Top Runners** — Leaderboard of tokens with highest 24h gains

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 16+
- Free API keys (see below)

### 1. Clone

```bash
git clone https://github.com/HAIL0K/candle-launch-terminal.git
cd candle-launch-terminal
```

### 2. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Create your `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| `DUNE_API_KEY` | [dune.com/settings/api](https://dune.com/settings/api) | Yes — launch data |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Yes — narrative classification |
| `HELIUS_API_KEY` | [helius.dev](https://helius.dev) | Optional — better RPC |
| `COINGECKO_API_KEY` | [coingecko.com](https://www.coingecko.com/en/api) | Optional |

### 3. Start Backend

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

First startup takes 5-10 minutes — it backfills 90 days of historical data from Dune, DefiLlama, and other sources. Subsequent starts are instant.

### 4. Frontend Setup

```bash
cd ../frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

## Architecture

```
backend/
  app/
    main.py              — FastAPI app + APScheduler jobs
    fetchers/            — DexScreener, DefiLlama, Solana RPC, etc.
    ingestion/           — Dune SQL queries, historical data backfill
    launch/              — Launch monitor (discovery, enrichment, verification)
    narrative/           — Narrative tracker (scanner, classifier, pipeline)
    analysis/            — Correlation analysis, scoring
    routers/             — API endpoints

frontend/
  src/
    pages/
      UnifiedDashboard   — Single-page dashboard (health + launch + narratives)
      LaunchDetail        — Detailed view for launch metrics
      NarrativeDetail     — Token table for a specific narrative
    components/          — Charts, cards, layout
    types/               — TypeScript interfaces
```

## Data Sources

| Source | What it provides | Cost |
|--------|-----------------|------|
| Dune Analytics | Token launches, graduations per launchpad | Free (2,500 credits/month) |
| DexScreener | Token prices, trending tokens, market caps | Free |
| GeckoTerminal | New pool discovery, OHLCV candle data | Free |
| Groq | Narrative classification (llama-3.3-70b) | Free (14,400 req/day) |
| DefiLlama | TVL, DEX volume, stablecoin supply, fees | Free |
| RugCheck | Token risk scoring, scam detection | Free |
| Solana RPC | TPS, priority fees, stablecoin supply | Free (public or Helius) |

## Refresh Schedule

| Data | Frequency |
|------|-----------|
| Token discovery (new pools) | Every 2 min |
| Token enrichment (mcap, volume) | Every 2 min |
| Narrative scan + AI classification | Every 20 min |
| DEX volume | Every 5 min |
| Launchpad creates (all platforms) | Every 6 hours |
| Launchpad graduations | Daily |
| SOL price, TPS, fees | Every 1-2 min |

## API Credit Usage

Stays within free tiers:
- **Dune**: ~2,100 credits/month (limit: 2,500)
- **Groq**: ~72 requests/day (limit: 14,400)
- **All other APIs**: Unlimited free tier

## License

Private — for internal use only.
