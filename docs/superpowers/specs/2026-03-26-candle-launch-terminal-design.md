# Candle Launch Terminal — Design Spec

## Overview

A Bloomberg-style quantitative terminal for Solana, built to give edge on when and how to launch tokens. It aggregates on-chain data, market metrics, social signals, and unconventional data sources into actionable composite scores.

**Target users:** Small team making Solana launch decisions, with potential to become a product for others.

**Platform:** Web app — React frontend + Python backend.

**Visual style:** Dark terminal/hacker aesthetic (default) with an optional Bloomberg dense-data mode toggle.

**MVP goal:** Get core data flowing and usable fast, iterate from there.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   React Frontend                     │
│  (Vite + TypeScript + TailwindCSS + Recharts)        │
│  Dark terminal theme / Bloomberg toggle              │
│  Multi-page: each tool = a route                     │
└──────────────────────┬──────────────────────────────┘
                       │ REST API (JSON)
┌──────────────────────┴──────────────────────────────┐
│                 Python Backend (FastAPI)              │
│                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Tool APIs   │  │ Data Layer  │  │  Scheduler  │ │
│  │ /api/pulse   │  │  Cache +    │  │ (APScheduler)│ │
│  │ /api/launch  │  │  Rate Limit │  │  Fetch jobs  │ │
│  │ /api/narrat. │  │  + Normalize│  │              │ │
│  │ /api/...     │  │             │  │              │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
│         └────────────────┴─────────────────┘        │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │        Data Sources        │
         │  Helius, DeFi Llama,       │
         │  GeckoTerminal, DexScreener│
         │  Jupiter, pytrends, RPC,   │
         │  CoinGecko, etc.           │
         └───────────────────────────┘
```

### Key Architectural Decisions

- **Database:** SQLite for MVP, migrate to PostgreSQL when needed
- **Caching:** In-memory cache (Redis later) to stay within free API rate limits
- **Scheduler:** APScheduler runs background jobs that fetch data on intervals — frontend reads from cache/DB, never hits external APIs directly on user requests
- **Modular tools:** Each tool is a FastAPI router — isolated module with its own data fetching, processing, and endpoints
- **Fetchers separate from routers:** Fetchers write to DB on schedule, routers read from DB on request
- **CORS:** FastAPI configured with `CORSMiddleware` allowing the Vite dev server origin (localhost:5173) in development, configurable for production
- **Theme-aware components:** All UI components accept a theme prop from Phase 1 so Bloomberg mode can be retrofitted without rewriting

---

## Error Handling & Resilience

External free-tier APIs are the biggest operational risk. Every fetcher must handle failures gracefully.

### Fetcher Resilience

- **Retry policy:** Each fetcher retries up to 3 times with exponential backoff (1s, 4s, 16s) + jitter on 4xx/5xx or timeout
- **Circuit breaker:** After 5 consecutive failures, a fetcher enters "open" state for 5 minutes before retrying. Prevents hammering a down API
- **Stale data thresholds:** Each data source has a staleness limit (e.g., DexScreener: 5 min, DeFi Llama: 30 min, pytrends: 6 hours). Data older than the threshold is flagged in the UI with a warning badge
- **Graceful degradation:** If a data source is unavailable, composite scores that depend on it exclude that factor and show "(N of M factors available)" rather than failing entirely. Individual metric cards show "Stale" or "Unavailable" with the last known value and timestamp

### Rate Limit Budget (Helius Free Tier)

Helius free tier: 10 RPC requests/second, ~100K credits/day. Budget allocation:
- `getRecentPerformanceSamples` (TPS): 1 call every 2 min = 720/day
- `getRecentPrioritizationFees`: 1 call every 2 min = 720/day
- `getTokenSupply` x2 (USDC + USDT): 2 calls every 5 min = 576/day
- Exchange wallet checks (5 wallets): 5 calls every 5 min = 1,440/day
- On-chain token/pool monitoring: via `getSignaturesForAddress` every 2 min = 720/day
- **Total: ~4,176 calls/day** — well within the 100K budget

### On-Chain Monitoring Approach

For MVP, use **polling with gap detection** rather than real-time webhooks:
- Poll `getSignaturesForAddress` on key programs (pump.fun, Raydium, Meteora) every 2 minutes
- Track the last seen signature to avoid missing events between polls
- Accept that events are detected with up to 2-minute delay — acceptable for a dashboard, not a trading bot
- When Helius paid tier is added, migrate to webhooks for real-time event streaming

### pytrends Fragility

pytrends is an unofficial scraper that Google frequently blocks. Mitigations:
- Fetch with random delays (30–90s between calls)
- Cache aggressively — Google Trends data is hourly at best, so 1-hour fetch is fine
- If blocked, show "Google Trends unavailable" with last known data and timestamp
- Long-term: consider SerpApi free tier (100 searches/month) as fallback

---

## Data Sources

### Free Tier (MVP)

| Source | What It Provides | Fetch Interval |
|---|---|---|
| **Solana RPC** (public + Helius free) | TPS, priority fees, stablecoin supply, token mints, account data | 2 min |
| **DexScreener** | Real-time prices, trending tokens, volume, boosts — no key needed | 1 min |
| **GeckoTerminal** | OHLCV candle data for any Solana DEX token — no key needed | 5 min |
| **Jupiter** | Best aggregated Solana token prices — no key needed | 1 min |
| **DeFi Llama** | TVL, DEX volume, fees, bridges, stablecoins — cross-chain — no key needed | 5 min |
| **CoinGecko** (free tier) | SOL price, market data, historical OHLCV | 5 min |
| **pytrends** | Google search trends for crypto keywords | 1 hour |
| **Fear & Greed Index** (alternative.me) | Daily market sentiment | 1 hour |
| **GitHub API** | Ecosystem development activity | 6 hours |
| **On-chain monitoring** | New token mints, DEX pool creation, pump.fun activity, exchange wallets | 2 min |

### Paid Tier (Add Later)

Ordered by priority and cost:

1. **Helius Developer** (~$49/mo) — higher rate limits, webhooks, parsed transactions
2. **Birdeye Starter** (~$49/mo) — real-time DEX data, OHLCV, token discovery
3. **CoinGecko Analyst** (~$14/mo) — higher rate limits, more history
4. **Santiment Pro** (~$49/mo) — on-chain + social sentiment combo
5. **Dune Plus** (~$349/mo) — SQL-based custom on-chain analytics + API
6. **LunarCrush Pro** (~$99/mo) — social sentiment scoring
7. **Flipside Pro** (~$49–99/mo) — alternative SQL analytics
8. **Nansen Standard** (~$150/mo) — wallet labels, smart money tracking

---

## Tool Pages

### Tool 1: Solana Market Pulse

The macro view of Solana's health.

**Metrics:**
- SOL price + 24h/7d/30d change
- Network TPS — current + historical trend
- Priority fees trend — block space demand
- Stablecoin supply on Solana — USDC + USDT total + trend
- Total DEX volume on Solana vs other chains
- Solana TVL trend
- Bridge inflows/outflows — capital entering or leaving
- Fear & Greed Index
- Google Trends: "solana" vs "ethereum" vs "bitcoin"

**Composite score:** Solana Health Score (0–100, color-coded)

**Data sources:** Solana RPC, CoinGecko, DeFi Llama, Fear & Greed API, pytrends

---

### Tool 2: Launch Environment Monitor

Is now a good time to launch a token?

**Metrics:**
- New token creation rate — tokens minted per hour/day
- New DEX pool creation rate — Raydium, Meteora, Orca
- Pump.fun activity — new tokens, graduation rate, avg bonding curve completion
- Token survival rate — % maintaining liquidity after 1h/24h/7d
- Market cap distribution — median/90th percentile peak market cap for new tokens
- Holding duration signals — buy-and-hold vs quick flipping

**Cold-start note:** Survival rate and holding duration require historical tracking. These metrics become meaningful after ~7 days of data collection. During cold-start, the UI shows "Collecting data (X days of Y needed)" and the Launch Window Score excludes these factors, recalculating from available metrics only.

**Composite score:** Launch Window Score — Good / Cautious / Wait

**Data sources:** On-chain monitoring (SPL Token program, DEX programs, pump.fun program), GeckoTerminal, DexScreener

---

### Tool 3: Narrative Tracker

What themes/narratives are hot?

**Metrics:**
- Token categorization by narrative (AI, pets, political, TikTok, gaming, etc.) — MVP uses keyword/regex matching on token name, symbol, and description metadata (e.g., tokens with "AI", "GPT", "neural" → AI category; "dog", "cat", "pepe" → meme/animals). Categories are defined in a config file for easy tuning. LLM-based classification is a future upgrade.
- Volume and market cap by narrative category — trending up/down
- Google Trends for narrative keywords
- Narrative momentum — gaining vs losing volume 24h/7d
- Top performers per narrative
- New token creation by narrative — what categories people are launching into

**Composite score:** Narrative Momentum Index per category — ranked with trend arrows

**Data sources:** DexScreener, GeckoTerminal, pytrends, token metadata analysis

---

### Tool 4: Whale & Exchange Flow

What are the big players doing?

**Metrics:**
- Exchange wallet SOL balances — known exchange hot/cold wallets (initial address list curated from Solscan labels and community sources, stored as a JSON config file in the backend — e.g., Binance, Coinbase, Kraken, OKX, Bybit hot wallets)
- Net exchange flow — deposits (bearish) vs withdrawals (bullish)
- Large transaction alerts — SOL/USDC above threshold
- Stablecoin exchange flows
- Jito MEV tips trend — sophisticated trading activity proxy

**Composite score:** Smart Money Flow — Bullish / Neutral / Bearish

**Data sources:** Solana RPC (labeled exchange addresses), on-chain Jito tip monitoring

---

### Tool 5: Chain Comparison

How is Solana vs other chains?

**Metrics:**
- TVL comparison — Solana vs ETH vs Base vs Arbitrum
- DEX volume comparison
- Fee revenue comparison
- Stablecoin distribution across chains
- SOL vs ETH price correlation and relative strength
- Developer activity — GitHub commits
- Google Trends comparison across chains

**Composite score:** Solana Relative Strength — Gaining / Stable / Losing

**Data sources:** DeFi Llama, CoinGecko, GitHub API, pytrends

---

### Tool 6: Trending Tokens

What's moving right now?

**Metrics:**
- Top gainers/losers by timeframe (1h/6h/24h)
- Volume leaders
- Newly created tokens with traction (filtered by min volume/liquidity)
- Token security checks — mint authority, freeze authority, top holder concentration
- OHLCV charts for any token
- Boosted/promoted tokens on DexScreener

**Composite score:** Breakout Score — unusual volume + price action relative to history

**Data sources:** DexScreener, GeckoTerminal, Jupiter, Solana RPC

---

## Statistical Methods

### Z-Score Anomaly Detection
Rolling mean and standard deviation on metrics like TPS, volume, token creation rate. Flag when current value is >2 sigma from the norm.

### Moving Averages & Crossovers
7d vs 30d moving averages on DEX volume, TVL, stablecoin supply. Crossovers signal regime changes.

### Correlation Analysis
Historical correlation with lag analysis between leading indicators and outcomes:
- Google Trends ↔ SOL price
- Stablecoin inflows ↔ DEX volume
- Token creation rate ↔ launch success rate
- Priority fees ↔ next-day volume

### Mean Reversion Signals
Bollinger Band-style analysis on on-chain metrics. Flag when metrics deviate far from historical mean.

### Regime Classification
Classify market state using multiple signals. Each metric contributes +1 (bullish), 0 (neutral), or -1 (bearish) based on z-score. Aggregate determines regime:
- **Hot market:** High volume, high token creation, rising TVL, positive exchange outflows
- **Cold market:** Low volume, declining creation rate, capital outflows
- **Transitioning:** Mixed signals

### Narrative Momentum (Rate of Change)
Track rate of change of volume and market cap per narrative category. A category growing 50% week-over-week from a small base is more significant than a large stable one.

### Composite Scores

| Score | Components | Output |
|---|---|---|
| Solana Health Score | TPS + fees + volume + TVL + stablecoins + bridges + Fear&Greed | 0–100, color-coded |
| Launch Window Score | Creation rate + survival rate + mcap distribution + holding duration + health | Good / Cautious / Wait |
| Narrative Momentum Index | Volume RoC + creation rate + Google Trends per category | Ranked list with arrows |
| Smart Money Flow | Net exchange flow + large tx direction + Jito MEV | Bullish / Neutral / Bearish |
| Solana Relative Strength | TVL share + volume share + fee share + stablecoin share vs others | Gaining / Stable / Losing |

All scores are fully transparent — every factor visible with its current value, historical norm, and contribution to the total score.

---

## Frontend Design

### Tech Stack
- Vite + React + TypeScript
- TailwindCSS
- Recharts for all charts (D3.js deferred to post-MVP if custom visualizations are needed)
- React Router for multi-page navigation

### Navigation
Sidebar navigation, always visible. Pages: Pulse, Launch, Narrative, Whales, Chains, Trending, Settings (theme toggle + data source status).

### Default Theme (Dark Terminal)
- Background: near-black (#0a0a0f) with subtle grid texture
- Primary accent: amber/gold (#f0b90b) — Candle brand
- Secondary: green (bullish), red (bearish), cyan (neutral)
- Font: JetBrains Mono or IBM Plex Mono
- Cards: dark gray (#12121a), sharp corners
- Charts: neon glow lines, dark backgrounds

### Bloomberg Mode (Toggle)
- Denser layout, smaller fonts
- Tables dominate over charts
- Multi-panel grid
- Orange/white on dark blue (classic Bloomberg)

### Page Layout Pattern
Each page follows: Composite Score → Factor Breakdown (expandable) → Main Chart + Key Metrics → Detail Section (tables, secondary charts, drill-downs).

### Responsiveness
Desktop-first. Support down to 1200px. No mobile layout for MVP.

### Data Freshness
"Last updated" timestamp on every page. Auto-refresh via polling at intervals matching the backend fetch schedule. Subtle pulse animation on refresh. WebSocket/SSE is a future consideration for true real-time updates.

---

## Project Structure

```
launch_terminal/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry
│   │   ├── config.py                # API keys, intervals, settings
│   │   ├── database.py              # SQLite connection, models
│   │   ├── scheduler.py             # APScheduler setup
│   │   ├── cache.py                 # In-memory cache + rate limiter
│   │   ├── routers/
│   │   │   ├── pulse.py
│   │   │   ├── launch.py
│   │   │   ├── narrative.py
│   │   │   ├── whales.py
│   │   │   ├── chains.py
│   │   │   └── trending.py
│   │   ├── fetchers/
│   │   │   ├── solana_rpc.py
│   │   │   ├── dexscreener.py
│   │   │   ├── geckoterminal.py
│   │   │   ├── defillama.py
│   │   │   ├── coingecko.py
│   │   │   ├── jupiter.py
│   │   │   ├── google_trends.py
│   │   │   ├── fear_greed.py
│   │   │   ├── github_activity.py
│   │   │   ├── exchange_wallets.py
│   │   │   └── onchain_monitor.py
│   │   └── analysis/
│   │       ├── scores.py
│   │       ├── zscore.py
│   │       ├── moving_averages.py
│   │       ├── correlation.py
│   │       ├── regime.py
│   │       └── narrative_classify.py
│   │   └── data/
│   │       └── exchange_wallets.json  # Curated exchange wallet addresses
│   ├── requirements.txt
│   ├── .env.example                   # Template with required env vars
│   └── .env                           # Actual keys (gitignored)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── api/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   ├── charts/
│   │   │   ├── scores/
│   │   │   └── common/
│   │   ├── pages/
│   │   │   ├── Pulse.tsx
│   │   │   ├── Launch.tsx
│   │   │   ├── Narrative.tsx
│   │   │   ├── Whales.tsx
│   │   │   ├── Chains.tsx
│   │   │   ├── Trending.tsx
│   │   │   └── Settings.tsx
│   │   ├── hooks/
│   │   ├── styles/
│   │   │   ├── terminal-theme.css
│   │   │   └── bloomberg-theme.css
│   │   └── types/
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── docs/
│   └── superpowers/
│       └── specs/
└── .gitignore
```

---

## MVP Build Order

### Phase 1: Foundation
- Backend skeleton — FastAPI app, database, config, cache, scheduler
- Frontend skeleton — Vite app, routing, sidebar, dark theme, page layout
- One fetcher end-to-end (DexScreener)

### Phase 2: Solana Market Pulse
- Fetchers: Solana RPC, CoinGecko, DeFi Llama, Fear & Greed, pytrends
- Analysis: z-score, moving averages, Health Score
- UI: Pulse page

### Phase 3: Trending Tokens
- Fetchers: GeckoTerminal OHLCV, Jupiter prices
- Analysis: breakout score
- UI: Trending page

### Phase 4: Launch Environment Monitor
- Fetchers: on-chain monitor (new tokens, pools, pump.fun)
- Analysis: launch window score, survival rate, regime classification
- UI: Launch page

### Phase 5: Narrative Tracker
- Analysis: narrative classification, momentum index
- UI: Narrative page

### Phase 6: Whale & Exchange Flow
- Fetchers: exchange wallets, Jito MEV
- Analysis: smart money flow
- UI: Whales page

### Phase 7: Chain Comparison
- Fetchers: GitHub API
- Analysis: relative strength
- UI: Chains page

### Phase 8: Polish
- Bloomberg mode toggle
- Score tuning with real data
- Performance optimization

**MVP definition:** The terminal is usable after Phase 2 (one working tool with real data). Phases 2–4 are the core MVP. Phases 5–7 are stretch goals. Phase 8 is post-MVP polish.

---

## Settings Page

The Settings page contains:
- **Theme toggle:** Switch between Dark Terminal and Bloomberg mode
- **Data source status:** Live/stale/unavailable status for each fetcher, with last fetch timestamp and error count
- **API key management:** Input fields for optional paid API keys (Helius, Birdeye, etc.) — stored in `.env`, not in the database

---

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm or pnpm

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env      # Add API keys
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev               # Starts on localhost:5173
```

### Environment Variables (.env.example)
```
HELIUS_API_KEY=           # Optional — free tier key from helius.dev
COINGECKO_API_KEY=        # Optional — demo key from coingecko.com
GITHUB_TOKEN=             # Optional — for higher rate limits
```

All API keys are optional for MVP. The system works with public/free endpoints when keys are not provided.

---

## Testing Approach

### Backend
- **Unit tests:** Each analysis module (zscore, moving_averages, scores, etc.) tested with known input/output — pure functions, no external dependencies
- **Fetcher tests:** Mock HTTP responses for each data source. Verify parsing, error handling, and rate limit behavior. Use `pytest` + `responses` or `httpx` mock
- **Integration tests:** Test the scheduler → fetcher → database → router pipeline end-to-end with mocked external APIs
- **Framework:** pytest

### Frontend
- **Component tests:** Key components (ScoreCard, FactorBreakdown, charts) tested with React Testing Library
- **Framework:** Vitest + React Testing Library

### Data validation
- Each fetcher validates response shape before writing to DB (e.g., expected fields present, values in reasonable ranges)
- Scores have sanity bounds — composite scores clamped to valid ranges, individual factors checked for NaN/infinity

---

## .gitignore

```
# Backend
backend/.env
backend/venv/
backend/__pycache__/
backend/**/__pycache__/
*.pyc
*.db

# Frontend
frontend/node_modules/
frontend/dist/

# IDE
.vscode/
.idea/
```
