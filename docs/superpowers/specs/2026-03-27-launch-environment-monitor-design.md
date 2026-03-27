# Launch Environment Monitor — Design Spec

## Overview

A launch intelligence dashboard that answers: "If I launch a token today, what can I expect?" Tracks token launches across Solana launchpads (pump.fun, Bonk, Bags, Candle TV v2), measures their outcomes at multiple timeframes, and presents the data as a dashboard of metric cards with drill-down detail pages.

**Target users:**
- New devs exploring token launches — need to understand what's normal, what's possible
- Established teams waiting for the right moment — need data-driven timing signals

**Route:** `/launch`

---

## Data Sources

| Source | What It Provides | Fetch Interval |
|---|---|---|
| **GeckoTerminal API** (free) | New Solana pool discovery — catches ALL migrated tokens | 2 min |
| **DexScreener API** (free) | Token performance data: price, volume, buys/sells, liquidity, market cap | 2 min |
| **Solana RPC** (Helius free) | Token creation counts per launchpad program | 5 min |
| **DefiLlama API** (free, existing) | DEX volume, bridge inflows/outflows, stablecoin supply | 5 min |

### GeckoTerminal for Discovery

GeckoTerminal provides a free endpoint that returns **all** new Solana DEX pools — not just tokens that paid for a profile.

**`GET https://api.geckoterminal.com/api/v2/networks/solana/new_pools`:**
- Returns ALL newly created pools on Solana (Raydium, Meteora, Orca, etc.)
- Free, no authentication required
- Rate limit: 30 requests/minute
- Response includes: pool address, base/quote tokens, price, FDV, market cap, volume, transaction counts
- We poll every 2 minutes (well within rate limit)
- Paginated — can fetch multiple pages to catch up if needed

This is critical: DexScreener's `/token-profiles/latest/v1` only returns tokens that have **paid** for a DexScreener profile, which would miss the vast majority of launches.

### DexScreener for Token Data

Once we discover tokens via GeckoTerminal, we use DexScreener for detailed performance tracking:

**`GET /tokens/v1/solana/{addresses}`:**
- Accepts comma-separated token addresses (up to 30 per request)
- Returns pairs with `dexId`, price, volume (`h1`, `h6`, `h24`), market cap, txns (buys/sells by timeframe), liquidity
- Rate limits undocumented — we stay conservative at ~10 req/min

**Batching strategy:**
- Discovery poll (GeckoTerminal): 1 request every 2 minutes
- Token data updates (DexScreener): batch 30 addresses per request
- At 500 tracked tokens needing updates: ~17 requests per cycle
- Total DexScreener: ~17 requests per 2-min cycle = ~9 req/min (conservatively safe)
- As token count grows, spread update batches across cycles (round-robin)

**Fallback:** If GeckoTerminal is down, discovery pauses but existing token tracking continues via DexScreener. If DexScreener is down, we retain last known data and show a "stale" indicator.

### Launchpad Identification

Tokens are tagged by launchpad source using multiple signals:
- GeckoTerminal pool data includes the DEX name (e.g., "PumpSwap" for pump.fun migrations)
- DexScreener `dexId` field (e.g., `"pumpswap"` for pump.fun tokens)
- Token address patterns (e.g., pump.fun addresses end in `pump`)
- Known launchpad program addresses for RPC counting

Supported launchpads (MVP):
- pump.fun (`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`)
- Bonk launcher
- Bags
- Candle TV v2 (program address TBD — when launched)

New launchpads can be added by adding their program address to a config dict.

### Migration Rate

Migration rate = tokens that complete bonding curve and land on a DEX / total tokens created on the launchpad.

- **Numerator:** Count of new DEX pairs from that launchpad (tracked tokens with launchpad tag)
- **Denominator:** Total token creates on the launchpad program (from RPC `getSignaturesForAddress`)

### RPC Budget (Helius Free Tier)

Helius free tier: 1M credits/month (~33k credits/day). `getSignaturesForAddress` costs 100 credits per call, returns up to 1,000 signatures.

**pump.fun creates ~15,000 tokens/day.** To count daily creates:
- Need ~15 calls per 5-min window to keep up with new signatures (1,500 credits/window)
- Daily cost for pump.fun alone: ~430k credits — **far exceeds free tier**

**Mitigation:** Instead of real-time RPC counting, use a lighter approach:
- Call `getSignaturesForAddress` with `limit=1` every 5 minutes just to confirm the program is active (100 credits)
- Use the count of tracked tokens that migrated to DEX as a proxy numerator
- For the denominator, scrape pump.fun's public stats page or use their API if available
- Fall back to daily batch counting during off-peak hours if needed
- Total daily RPC cost: ~3k credits (well within ~33k/day budget)

If denominator data is unavailable for a launchpad, migration rate is shown as "N/A" for that launchpad.

---

## Metrics

### Launch-Specific Metrics

| Metric | Description | Source |
|---|---|---|
| **Migration Rate** | % of launchpad tokens that graduate to a DEX. Historical trend by day. Broken down by launchpad. | RPC/external + DexScreener |
| **Median Peak Market Cap** | Median peak mcap of launched tokens at 1h, 24h, 7d checkpoints. Answers "how high do they typically go?" | DexScreener |
| **Time to Peak** | Median time from launch to highest observed market cap within 24h window. Answers "how fast do tokens pump?" | DexScreener |
| **Survival Rate** | % of tokens still actively trading (volume > $100 in last hour) at 1h, 24h, 7d. | DexScreener |
| **Buy/Sell Ratio** | Average buy vs sell count and volume across launched tokens. Accumulation vs distribution signal. | DexScreener |
| **Daily Launches** | Number of new tokens hitting DEXs per day, broken down by launchpad. | DexScreener |

### Market Context Metrics

| Metric | Description | Source |
|---|---|---|
| **On-Chain Volume** | Total Solana DEX trading volume. Higher volume = more active market for launches. | DefiLlama (existing) |
| **Capital Flow** | Net bridge inflows/outflows on Solana. Money flowing in = bullish for launches. | DefiLlama |

---

## Data Model

### Table: `launch_tokens`

One row per launched token. Created when DexScreener reports a new Solana token from a known launchpad. Updated at checkpoint intervals.

| Column | Type | Description |
|---|---|---|
| address | String(60), PK | Token mint address |
| pair_address | String(60) | DEX pair address |
| launchpad | String(30), indexed | "pumpfun", "bonk", "bags", "candle" |
| dex | String(30) | "raydium", "meteora", "orca" |
| created_at | DateTime | When the pair was first seen |
| mcap_peak_1h | Float, nullable | Peak market cap in first hour |
| mcap_peak_24h | Float, nullable | Peak market cap in first 24 hours |
| mcap_peak_7d | Float, nullable | Peak market cap in first 7 days |
| mcap_current | Float, nullable | Latest market cap |
| time_to_peak_minutes | Int, nullable | Minutes from creation to highest mcap observed so far (updated each cycle, finalized at 24h) |
| volume_1h | Float, nullable | Cumulative volume at 1h |
| volume_24h | Float, nullable | Cumulative volume at 24h |
| volume_7d | Float, nullable | Cumulative volume at 7d |
| buys_1h | Int, nullable | Buy transactions at 1h |
| sells_1h | Int, nullable | Sell transactions at 1h |
| buys_24h | Int, nullable | Buy transactions at 24h |
| sells_24h | Int, nullable | Sell transactions at 24h |
| liquidity_usd | Float, nullable | Current pool liquidity |
| is_alive | Bool | Still actively trading (volume > $100/hr). Set to False if not updated for 2+ hours (staleness guard). |
| checkpoint_complete | Bool, default False | True after 7d data is captured — stops updates |
| last_updated | DateTime | Last snapshot |

**Retention policy:** Tokens older than 90 days with `checkpoint_complete=True` are eligible for cleanup. A weekly job deletes these rows after their data has been aggregated into `launch_daily_stats`. This keeps the table manageable (~30k rows max at steady state vs unbounded growth).

### Table: `launch_daily_stats`

Pre-aggregated daily metrics for dashboard charts. Computed by a daily aggregation job. This is the permanent record — individual token rows can be cleaned up after aggregation.

| Column | Type | Description |
|---|---|---|
| id | Int, PK | Auto-increment |
| date | Date, indexed | Day |
| launchpad | String(30) | Source or "all" for aggregate |
| tokens_created | Int | Total created (from RPC/external counter) |
| tokens_migrated | Int | Made it to DEX |
| migration_rate | Float | tokens_migrated / tokens_created |
| median_peak_mcap_1h | Float, nullable | Median peak mcap at 1h |
| median_peak_mcap_24h | Float, nullable | Median peak mcap at 24h |
| median_peak_mcap_7d | Float, nullable | Median peak mcap at 7d |
| median_time_to_peak | Float, nullable | Median minutes to peak |
| survival_rate_1h | Float, nullable | % still trading at 1h |
| survival_rate_24h | Float, nullable | % still trading at 24h |
| survival_rate_7d | Float, nullable | % still trading at 7d |
| avg_buy_sell_ratio_1h | Float, nullable | Avg buys/sells at 1h |
| total_launches | Int | New pairs on DEX |
| total_volume | Float, nullable | Combined volume of launched tokens |

Unique constraint on (date, launchpad).

---

## Backend Architecture

### New Scheduled Jobs

These are standalone async functions scheduled via APScheduler (same pattern as `build_daily_candles` and `compute_today_score`), **not** BaseFetcher subclasses. The existing BaseFetcher pattern stores simple key-value metrics in MetricData; launch tracking needs its own tables and more complex logic.

**`poll_new_launches`** — runs every 2 minutes:
1. Calls GeckoTerminal `GET /api/v2/networks/solana/new_pools` to discover ALL new Solana pairs
2. Identifies launchpad source from DEX name (e.g., "PumpSwap"), token address patterns, and known program addresses
3. Filters out non-launchpad tokens (e.g., manual Raydium pool creates that aren't from a launchpad)
4. For new tokens not yet in `launch_tokens`: creates rows with `created_at=now`
5. Batches all non-complete tokens (up to 30 per request) and calls DexScreener `GET /tokens/v1/solana/{addresses}` for detailed performance data
6. Updates each tracked token:
   - Recalculates peak mcap (running max per checkpoint window)
   - Snapshots 1h/24h/7d metrics when those time windows elapse
   - Updates time_to_peak_minutes if current mcap > previous peak (within 24h window)
   - Checks if still alive (volume > $100 in last hour from DexScreener txns data)
7. After 7d from creation: sets `checkpoint_complete=True`, stops further updates

**Note:** Discovery (steps 1-4) and enrichment/update (steps 5-7) should be independent. If DexScreener is slow or failing, the GeckoTerminal discovery poll must not be blocked — new tokens should still be inserted into `launch_tokens` even if enrichment data is temporarily unavailable.

**`poll_launchpad_creates`** — runs every 5 minutes:
- For each launchpad with a known program address:
  - Calls `getSignaturesForAddress` with `limit=1` to confirm activity
  - Increments a daily counter in `MetricData` (source: `"launchpad_creates"`, metric_name: `"{launchpad}_count"`)
- For pump.fun specifically: fetches total daily creates from pump.fun's public API/stats if available, otherwise estimates from migration count / historical migration rate
- Budget: ~3k Helius credits/day (leaves ~30k/day headroom under the ~33k daily limit)

**`cleanup_old_tokens`** — runs weekly:
- Deletes `launch_tokens` rows where `checkpoint_complete=True` AND `created_at < 90 days ago`
- Only runs after confirming those tokens' data exists in `launch_daily_stats`

### Extended Fetcher

**`DefiLlamaFetcher`** (extend existing):
- Add bridge flow data using specific bridge IDs:
  - `GET https://bridges.llama.fi/bridge/77` — Wormhole (Portal), largest Solana bridge
  - `GET https://bridges.llama.fi/bridge/20` — deBridge
  - Parse `currentDayTokensDeposited` and `currentDayTokensWithdrawn` for net flow
- Additional endpoint: `GET https://stablecoins.llama.fi/stablecoinchains` for Solana stablecoin supply

### Aggregation Job

**`aggregate_launch_stats`** — runs once daily via APScheduler:
- Queries `launch_tokens` for tokens created in each day
- Computes medians (using Python's `statistics.median`), percentages, averages
- Inserts/updates rows in `launch_daily_stats`
- Generates both per-launchpad and "all" aggregate rows

### API Endpoints

All under `/api/launch/`, registered as a FastAPI router (same pattern as existing `/api/pulse/` router). All accept `?range=7d|30d|90d` query param.

| Endpoint | Returns |
|---|---|
| `GET /overview` | Latest stats for all metrics (dashboard cards) |
| `GET /migration-rate` | Daily migration rate chart + per-launchpad breakdown |
| `GET /peak-mcap` | Median peak mcap at 1h/24h/7d checkpoints, daily chart |
| `GET /time-to-peak` | Median time-to-peak daily chart |
| `GET /survival` | Survival rates at 1h/24h/7d, daily chart |
| `GET /buy-sell` | Buy/sell ratio trend, daily chart |
| `GET /launches` | Daily launch count, per-launchpad breakdown |
| `GET /volume` | On-chain DEX volume (reads existing DefiLlama data) |
| `GET /capital-flow` | Bridge inflows/outflows + stablecoin supply trend |

All endpoints return the same shape:
```json
{
  "current": 3.2,
  "trend": "up",
  "last_updated": "2026-03-27T14:30:00Z",
  "chart": [{"date": "2026-03-27", "value": 3.2}, ...],
  "breakdown": {"pumpfun": 2.8, "bonk": 4.1}
}
```

The `last_updated` field lets the frontend detect stale data (e.g., if DexScreener was down and data hasn't refreshed). The UI shows a "stale" badge if `last_updated` is more than 10 minutes old.

---

## Frontend

### Routing

Uses React Router nested routes under `/launch`:

```
/launch                    → LaunchDashboard (grid of metric cards)
/launch/migration-rate     → LaunchDetailPage for migration rate
/launch/peak-mcap          → LaunchDetailPage for peak mcap
/launch/time-to-peak       → LaunchDetailPage for time to peak
/launch/survival           → LaunchDetailPage for survival rate
/launch/buy-sell           → LaunchDetailPage for buy/sell ratio
/launch/launches           → LaunchDetailPage for daily launches
/launch/volume             → LaunchDetailPage for on-chain volume
/launch/capital-flow       → LaunchDetailPage for capital flow
```

Added to `App.tsx` route config alongside existing `/pulse` routes.

### Dashboard Page (`/launch`)

Grid of 8 metric cards, responsive layout (2 cols mobile, 4 cols desktop).

Each card shows:
- Metric name
- Current value (formatted appropriately — %, $, count)
- Mini sparkline (last 30 data points)
- Trend arrow (up/down/flat)
- Click navigates to detail page

### Detail Pages (`/launch/{metric}`)

Each detail page uses a shared `LaunchDetailPage` layout:
- Header: metric name, current value, trend
- Chart: time series with range selector (7d / 30d / 90d)
- Breakdown section: metric-specific content below the chart
  - Migration rate: per-launchpad table
  - Peak mcap: 1h/24h/7d comparison bars
  - Launches: stacked bar chart by launchpad
  - Capital flow: inflow vs outflow overlay

### Reusable Components

- `LaunchMetricCard` — dashboard tile with sparkline
- `LaunchDetailPage` — shared detail page layout (chart + range selector + breakdown slot)
- `LaunchBreakdownTable` — per-launchpad breakdown table

### Polling

- Dashboard: polls `/api/launch/overview` every 60s
- Detail pages: poll their specific endpoint every 60s

### Navigation

Sidebar "Launch" item already exists, points to `/launch`.

---

## Cold Start

This tool needs data collection time. On first run:
- Launch tracking starts immediately (GeckoTerminal pool discovery + DexScreener enrichment)
- 1h metrics available after 1 hour
- 24h metrics available after 1 day
- 7d metrics available after 1 week
- Historical trends become meaningful after ~2 weeks

The UI handles cold start gracefully:
- Cards show "Collecting data" with a progress indicator when insufficient data
- Charts show available data even if sparse
- No fake/placeholder data

---

## Error Handling

- **GeckoTerminal down:** New token discovery pauses, but existing token tracking continues via DexScreener. Resumes when API returns.
- **DexScreener down:** Show last known data with "stale" indicator (via `last_updated` field). Discovery still works via GeckoTerminal but detailed metrics freeze. If we hit a 429 rate limit, back off for 60s and retry.
- **RPC errors:** Migration rate denominator freezes at last known value. Other metrics unaffected. Helius free tier budget tracked to avoid exceeding daily limit.
- **DefiLlama down:** Volume and capital flow cards show stale data. Already handled by existing fetcher resilience.
- **Data quality:** Tokens with $0 liquidity or flagged as honeypots (if detectable from DexScreener labels) are excluded from aggregation stats.
