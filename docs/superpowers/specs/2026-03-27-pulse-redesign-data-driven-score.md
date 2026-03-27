# Pulse Page Redesign: Data-Driven Health Score

**Date:** 2026-03-27
**Status:** Design approved

## Problem

The current Pulse page dumps metric cards with no narrative. The health score uses hardcoded heuristic baselines (e.g., "2000 TPS is average") that are assumptions — not validated against actual price data. The score has no historical view, so a number like 67 has no context. The page should answer: **"Where is Solana at and where is it going?"**

## Solution

Replace the current Pulse page with a price-focused dashboard centered on a SOL candlestick chart with a data-driven health score indicator. The score is computed using only factors that have historical data and proven statistical correlation with SOL price movements. Live-only metrics (TPS, fees, exchange flow) are shown as supplementary info but do not affect the score.

---

## Section 1: Data Pipeline & Score Engine

### Historical Data Ingestion (one-time backfill on startup)

1. **SOL OHLCV** — import from `data/CRYPTO_SOLUSD, 1D_81fb0.csv` (2177 daily candles, April 2020–present). Columns: `time` (unix), `open`, `high`, `low`, `close`, plus a trailing empty column `#1` to ignore. Parser should use only the first 5 columns.
2. **Fear & Greed Index** — fetch from `https://api.alternative.me/fng/?limit=0` (full daily history since 2018).
3. **Solana TVL** — fetch from DeFi Llama `https://api.llama.fi/v2/historicalChainTvl/Solana` (full daily history).
4. **DEX Volume** — fetch from DeFi Llama `https://api.llama.fi/overview/dexs/solana` (available from ~Sept 2021). Include as scored factor only if at least 365 daily data points exist.
5. **Stablecoin supply on Solana** — fetch from DeFi Llama `https://stablecoins.llama.fi/stablecoincharts/Solana` (returns daily total stablecoin circulating supply). The scored factor is the **7-day change** (delta) in supply — positive delta = capital inflow, negative = outflow. Include only if at least 365 data points exist.

**Minimum data requirement:** A factor must have at least 365 daily data points to be included in correlation analysis and scoring. Factors with less data are excluded from the score but may still appear as informational.

**Partial availability during backfill:** When computing historical scores, each day uses only the factors that have data at that date. The `factors_available` / `factors_total` columns in `daily_scores` track this. Early dates (e.g., 2020) will have fewer factors than recent dates.

All historical data is stored in the database for reuse. The backfill runs once — subsequent startups skip if data already exists.

### Correlation Analysis

For each candidate factor, compute **rolling Pearson correlation** against SOL **7-day forward returns** (percentage price change over the next 7 days):

- Test multiple lags: 1d, 3d, 7d, 14d
- Select the lag with the strongest |correlation|
- Factors with |r| below **0.15** are flagged as "informational only" — shown on the page but excluded from the score (0.15 filters out noise while keeping meaningfully correlated signals)

**Boundary handling:** Correlation is computed on data up to T-7, since the most recent 7 days have no completed forward returns yet. As new days complete, correlations are updated. Recomputed daily.

Output per factor:
- Correlation coefficient (r)
- Optimal lag (days)
- Direction (positive r = higher value is bullish, negative r = higher value is bearish)

### Weight Derivation

Each scored factor's weight = |correlation coefficient| normalized so weights sum to 1.0. Stronger historical correlation = higher weight in the score.

### Score Computation

For each historical day (and for live data going forward):
1. Compute z-score for each factor using its **own 90-day rolling mean and std** (not hardcoded baselines). 90-day window balances responsiveness with stability.
2. Compute weighted signed z-score: `sign(r) * |weight| * z_score` — this ensures negatively-correlated factors (where higher value = bearish) contribute correctly without a separate sign-flip step.
3. Sum all weighted signed z-scores → pass through `50 + 50 * tanh(z / 2)` → clamp to 0–100

### Score Storage

New database table: `daily_scores`

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | Auto-increment |
| date | Date | Unique, indexed |
| score | Float | 0–100 |
| factors_json | Text | JSON: per-factor value, z-score, weight, contribution |
| factors_available | Integer | How many factors had data for this date |
| factors_total | Integer | Total scored factors |

### Transparency

Every factor exposes:
- Its correlation coefficient and optimal lag
- Its weight in the score
- Its current value, z-score, and contribution
- Why it's in the score vs. informational only

---

## Section 2: Chart & Frontend

### Charting Library

Replace Recharts with **TradingView lightweight-charts** (`lightweight-charts` npm package). Recharts cannot render candlesticks. Lightweight-charts is purpose-built for financial data — candlesticks, volume bars, line series, area series — and handles thousands of data points efficiently.

### Main Chart: SOL/USD Candlestick

- Candlestick chart from historical CSV + live CoinGecko data going forward
- **Green/red translucent background gradient** behind the candles based on the health score at that date:
  - Score ≥ 70 → green fade
  - Score ≤ 30 → red fade
  - Between → smooth gradient transition
- Time range selector: **30D** (default), **90D**, **1Y**, **All**

### Health Score Panel (below candlestick, synced x-axis)

- Line chart of the historical score (0–100)
- Line color follows the same green/red scheme
- **Shared crosshair** — hover on a date highlights both charts simultaneously

### Ecosystem Cards (below charts)

Mini sparkline cards for **live supplementary metrics** — these do NOT feed the score:
- Network TPS
- Priority Fees
- Stablecoin Supply (USDC + USDT)
- Exchange Inflow/Outflow (when available — deferred)
- Google Trends
- Any other live-only metrics

Each card shows: current value, 7-day mini sparkline, direction arrow.

Clearly visually separated from the scored factors section.

### Scored Factors Section

Shows only the factors that feed the score. For each:
- Current value and recent trend
- Correlation coefficient (r) and optimal lag
- Weight in the score
- Current contribution (positive or negative)

---

## Section 3: API Endpoints

### New Endpoints

**`GET /api/pulse/chart?range=30d`**

Returns candlestick data + health score history for the requested range.

```json
{
  "candles": [
    {"time": 1711497600, "open": 185.2, "high": 192.1, "low": 183.0, "close": 190.5}
  ],
  "scores": [
    {"time": 1711497600, "score": 67.3}
  ],
  "range": "30d"
}
```

Valid ranges: `30d`, `90d`, `1y`, `all`

**`GET /api/pulse/correlations`**

Returns each factor's correlation analysis and weight. Cached, recomputed daily.

```json
{
  "factors": [
    {
      "name": "tvl",
      "label": "Total Value Locked",
      "correlation": 0.42,
      "optimal_lag_days": 3,
      "weight": 0.28,
      "in_score": true
    }
  ],
  "last_computed": "2026-03-27T00:00:00Z"
}
```

**`GET /api/pulse/ecosystem`**

Returns live supplementary metrics with sparkline data. Replaces the old flat `/api/pulse` for the ecosystem cards.

```json
{
  "metrics": [
    {
      "name": "tps",
      "label": "Network TPS",
      "current": 3200,
      "sparkline": [2800, 3100, 2900, 3200],
      "direction": "up"
    }
  ],
  "last_updated": "2026-03-27T12:00:00Z"
}
```

### Removed Endpoint

**`GET /api/pulse`** — removed. The three new endpoints (`/chart`, `/correlations`, `/ecosystem`) fully replace it. The frontend calls them in parallel on load.

### Data Flow

1. Frontend loads → calls `/chart?range=30d` + `/ecosystem` + `/correlations` in parallel
2. Candlestick chart + score panel render immediately from historical data
3. Ecosystem cards populate with live metrics
4. `/ecosystem` polls every 30s for live updates
5. `/chart` does NOT poll — refreshes only on range change
6. `/correlations` fetched once on load (changes daily at most)

---

## Section 4: Implementation Scope

### Build

- Historical data ingestion script (SOL CSV import, DeFi Llama TVL full history, Fear & Greed full history, DeFi Llama stablecoin/DEX history where available)
- Correlation engine (Pearson with multi-lag analysis, weight derivation, minimum threshold filtering)
- Historical score backfill (compute score for every historical day using rolling stats, store in `daily_scores` table)
- New `daily_scores` DB table
- New API endpoints: `/pulse/chart`, `/pulse/correlations`, `/pulse/ecosystem`
- Remove old `/api/pulse` endpoint (replaced by the three new endpoints)
- Frontend: swap Recharts for lightweight-charts
- Candlestick chart with score-based green/red background gradient
- Synced health score panel below
- Time range selector (30D default, 90D, 1Y, All)
- Ecosystem sparkline cards (live supplementary metrics)
- Scored factors display with correlation/weight transparency

### Keep As-Is

- All existing fetchers (continue running for live data)
- Cache layer, resilience layer, scheduler
- `metric_data` DB table (additive — new table added, existing untouched)
- Sidebar, routing, theme system

### Remove

- Old Pulse page layout (8 metric card grids, old TVL line chart)
- Old score computation with hardcoded heuristic baselines
- Recharts dependency (replaced by lightweight-charts)
- `frontend/src/components/charts/TimeSeriesChart.tsx` (replaced)
- `frontend/src/api/pulse.ts` (reworked)

### Deferred

- Exchange inflow/outflow fetcher — needs curated exchange wallet address list, starts collecting from day one but no historical backfill available for free
- ML prediction models — future iteration once enough live data accumulates
- Expanded Google Trends keywords (memecoins, crypto, phantom wallet, etc.)
- Candlestick chart interactivity (drawing tools, annotations)
