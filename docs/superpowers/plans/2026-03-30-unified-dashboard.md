# Unified Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate Sol Outlook, Launch Monitor, and Narrative Tracker into a single unified dashboard page.

**Architecture:** Create one new page (`UnifiedDashboard.tsx`) that fetches from all three existing API endpoints and composes existing components into a hero + sections layout. Update routing to make `/` the unified page, keep detail routes, remove old top-level pages from navigation.

**Tech Stack:** React, TypeScript, Tailwind CSS, existing hooks (`useApiPolling`, `fetchChart`)

---

### Task 1: Create UnifiedDashboard Page

**Files:**
- Create: `frontend/src/pages/UnifiedDashboard.tsx`

This is the main task. The page fetches from three endpoints and renders three tiers:
- Tier 1 (Hero): Health score + condensed SOL chart + headline stats
- Tier 2 (Launch): LaunchPerformanceCard + LaunchMigrationCard side by side
- Tier 3 (Narratives): Narrative cards grid + top runners

- [ ] **Step 1: Create the unified dashboard**

```typescript
// frontend/src/pages/UnifiedDashboard.tsx
import { useState, useEffect, useCallback, useRef } from "react";
import CandlestickChart, { type CandlestickChartHandle } from "../components/charts/CandlestickChart";
import LaunchPerformanceCard from "../components/launch/LaunchPerformanceCard";
import LaunchMigrationCard from "../components/launch/LaunchMigrationCard";
import LaunchMetricCard from "../components/launch/LaunchMetricCard";
import { useApiPolling } from "../hooks/useApiPolling";
import { fetchChart } from "../api/pulse";
import type { ChartData } from "../types/pulse";
import type { LaunchOverviewData } from "../types/launch";
import type { NarrativeOverview, NarrativeData, NarrativeTokenData } from "../types/narrative";
import { useNavigate } from "react-router-dom";

// ── Helpers ──

function formatCompact(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

function formatPct(v: number | null): string {
  if (v == null) return "--";
  return `${v > 0 ? "+" : ""}${v.toFixed(0)}%`;
}

function formatAge(created: string | null): string {
  if (!created) return "--";
  const diff = Date.now() - new Date(created).getTime();
  const h = Math.floor(diff / 3600000);
  if (h >= 24) return `${Math.floor(h / 24)}d ago`;
  if (h > 0) return `${h}h ago`;
  return `${Math.floor(diff / 60000)}m ago`;
}

// ── Narrative sub-components (extracted from NarrativeDashboard) ──

const LIFECYCLE_COLORS: Record<string, string> = {
  emerging: "text-blue-400 bg-blue-400/10 border-blue-400/20",
  trending: "text-terminal-green bg-terminal-green/10 border-terminal-green/20",
  saturated: "text-terminal-accent bg-terminal-accent/10 border-terminal-accent/20",
  fading: "text-terminal-red bg-terminal-red/10 border-terminal-red/20",
};

function NarrativeCard({ narrative, onClick }: { narrative: NarrativeData; onClick: () => void }) {
  const lc = LIFECYCLE_COLORS[narrative.lifecycle] || LIFECYCLE_COLORS.fading;
  return (
    <button onClick={onClick}
      className="bg-terminal-card border border-terminal-border rounded-lg p-4 text-left hover:border-terminal-accent/40 transition-all w-full">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-terminal-text">{narrative.name}</span>
        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${lc} capitalize`}>{narrative.lifecycle}</span>
      </div>
      <div className="flex items-center gap-4 text-xs text-terminal-muted">
        <span>{narrative.token_count} tokens</span>
        <span>{formatCompact(narrative.total_volume)} vol</span>
        <span className={narrative.avg_gain_pct > 0 ? "text-terminal-green" : "text-terminal-red"}>
          {formatPct(narrative.avg_gain_pct)} avg
        </span>
      </div>
    </button>
  );
}

function RunnerRow({ token }: { token: NarrativeTokenData }) {
  return (
    <div className="flex items-center gap-3 py-2 border-b border-terminal-border/20 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-terminal-text truncate">{token.name}</span>
          <span className="text-[10px] text-terminal-muted">{token.symbol}</span>
          {!token.is_original && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-terminal-accent/10 text-terminal-accent border border-terminal-accent/20">fork</span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[11px] text-terminal-muted mt-0.5">
          {token.narrative && <span className="text-terminal-accent">{token.narrative}</span>}
          <span>{formatAge(token.created_at)}</span>
        </div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className={`text-sm font-bold tabular-nums ${(token.price_change_pct ?? 0) > 0 ? "text-terminal-green" : "text-terminal-red"}`}>
          {formatPct(token.price_change_pct)}
        </div>
        <div className="text-[11px] text-terminal-muted tabular-nums">
          {token.mcap ? formatCompact(token.mcap) : "--"}
        </div>
      </div>
      <a href={`https://dexscreener.com/solana/${token.address}`} target="_blank" rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()} className="text-[10px] text-terminal-accent/60 hover:text-terminal-accent flex-shrink-0">DS</a>
    </div>
  );
}

// ── Main Component ──

export default function UnifiedDashboard() {
  const navigate = useNavigate();
  const chartRef = useRef<CandlestickChartHandle>(null);

  // Data sources
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const { data: launchData } = useApiPolling<LaunchOverviewData>("/launch/overview?range=30d", 60000);
  const { data: narrativeData } = useApiPolling<NarrativeOverview>("/narrative/overview", 60000);

  // Fetch chart with default exclusions
  useEffect(() => {
    const defaultExcluded = ["dex_volume", "stablecoin_supply", "vol_regime", "new_wallets", "priority_fees"];
    fetchChart("all", defaultExcluded).then(setChartData).catch(() => {});
    const interval = setInterval(() => {
      fetchChart("all", defaultExcluded).then(setChartData).catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // Apply 90d visible range after chart mounts
  useEffect(() => {
    if (!chartData) return;
    const timer = setTimeout(() => {
      const chart = chartRef.current?.getChart();
      if (chart) {
        const now = Math.floor(Date.now() / 1000);
        chart.timeScale().setVisibleRange({ from: (now - 90 * 86400) as any, to: now as any });
      }
    }, 50);
    return () => clearTimeout(timer);
  }, [chartData]);

  // Extract health score
  const currentScore = chartData?.scores?.length
    ? chartData.scores[chartData.scores.length - 1].score
    : null;

  // Extract launch stats
  const activity = launchData?.metrics.find((m) => m.name === "Launchpad Activity");
  const launchCount = activity?.current ?? 0;
  const migrationRate = (activity as Record<string, unknown> | undefined)?.migration_rate as number | undefined;
  const survivalMetric = launchData?.metrics.find((m) => m.name === "Survival Rate (24h)");

  return (
    <div className="max-w-7xl mx-auto">
      {/* ── Tier 1: Hero ── */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-6">
            <div className="text-terminal-accent font-bold text-xl tracking-wider">CANDLE</div>
            {currentScore !== null && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-terminal-muted uppercase">Health</span>
                <span className={`text-3xl font-bold ${
                  currentScore >= 70 ? "text-terminal-green" : currentScore <= 30 ? "text-terminal-red" : "text-terminal-accent"
                }`}>{currentScore.toFixed(0)}</span>
              </div>
            )}
            <div className="flex items-center gap-4 text-sm text-terminal-muted">
              <span><span className="text-terminal-text font-bold">{formatCompact(launchCount)}</span> launches</span>
              {migrationRate != null && <span><span className="text-terminal-text font-bold">{migrationRate.toFixed(1)}%</span> grad rate</span>}
              {survivalMetric?.current != null && <span><span className="text-terminal-text font-bold">{survivalMetric.current.toFixed(0)}%</span> survival</span>}
            </div>
          </div>
        </div>

        {/* Condensed SOL chart */}
        {chartData && chartData.candles.length > 0 && (
          <CandlestickChart ref={chartRef} candles={chartData.candles} scores={chartData.scores} height={200} />
        )}
      </div>

      {/* ── Tier 2: Launch Conditions ── */}
      <div className="mb-6">
        <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">Launch Conditions</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {launchData?.metrics.map((metric) =>
            metric.name === "Launch Performance" ? (
              <LaunchPerformanceCard key={metric.name} metric={metric} />
            ) : metric.name === "Launchpad Activity" ? (
              <LaunchMigrationCard key={metric.name} metric={metric} />
            ) : (
              <LaunchMetricCard key={metric.name} metric={metric} />
            )
          )}
        </div>
      </div>

      {/* ── Tier 3: What to Launch ── */}
      <div>
        <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">Trending Narratives</div>

        {/* Disclaimer */}
        <div className="bg-terminal-red/5 border border-terminal-red/20 rounded-lg px-4 py-3 mb-4">
          <p className="text-xs text-terminal-red/80 leading-relaxed">
            This tool identifies trending narratives for token developers. Tokens shown here include
            unverified and potentially dangerous coins. This is not investment advice — do not buy
            tokens based on this data.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Narrative cards */}
          <div className="lg:col-span-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {narrativeData?.narratives.map((n) => (
                <NarrativeCard key={n.name} narrative={n}
                  onClick={() => navigate(`/narrative/${encodeURIComponent(n.name)}`)} />
              ))}
            </div>
            {(!narrativeData || narrativeData.narratives.length === 0) && (
              <div className="text-terminal-muted text-center py-8 text-sm">
                No narratives detected yet — data populates every 20 minutes
              </div>
            )}
          </div>

          {/* Top Runners */}
          <div>
            <div className="text-xs text-terminal-muted uppercase tracking-wider mb-2">Top Runners (24h)</div>
            <div className="bg-terminal-card border border-terminal-border rounded-lg p-4">
              {narrativeData?.top_runners.map((t) => (
                <RunnerRow key={t.address} token={t} />
              ))}
              {(!narrativeData || narrativeData.top_runners.length === 0) && (
                <div className="text-terminal-muted text-center py-6 text-sm">No runners yet</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean (may need fnm env setup)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/UnifiedDashboard.tsx
git commit -m "feat: create UnifiedDashboard page with hero + launch + narratives"
```

---

### Task 2: Update Routing and Remove Sidebar

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Update App.tsx**

Replace entire content:

```typescript
// frontend/src/App.tsx
import { Routes, Route, Navigate } from "react-router-dom";
import UnifiedDashboard from "./pages/UnifiedDashboard";
import LaunchDetail from "./pages/LaunchDetail";
import NarrativeDetail from "./pages/NarrativeDetail";

export default function App() {
  return (
    <main className="min-h-screen overflow-y-auto p-6 bg-terminal-bg">
      <Routes>
        <Route path="/" element={<UnifiedDashboard />} />
        {/* Detail views */}
        <Route path="/launch/:metric" element={<LaunchDetail />} />
        <Route path="/narrative/:name" element={<NarrativeDetail />} />
        {/* Old routes redirect to unified dashboard */}
        <Route path="/pulse" element={<Navigate to="/" replace />} />
        <Route path="/launch" element={<Navigate to="/" replace />} />
        <Route path="/narrative" element={<Navigate to="/" replace />} />
      </Routes>
    </main>
  );
}
```

This removes the sidebar entirely. The `CANDLE` branding is in the hero of the unified dashboard.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: route everything to unified dashboard, remove sidebar"
```

---

### Task 3: Update Detail Pages Back Navigation

**Files:**
- Modify: `frontend/src/pages/LaunchDetail.tsx`
- Modify: `frontend/src/pages/NarrativeDetail.tsx`

The detail pages currently have "Back to monitor" and "Back to narratives" links pointing to `/launch` and `/narrative`. Update them to point to `/`.

- [ ] **Step 1: Update LaunchDetail.tsx**

Change the back button `navigate("/launch")` to `navigate("/")` and text to "Back to dashboard".

- [ ] **Step 2: Update NarrativeDetail.tsx**

Change `navigate("/narrative")` to `navigate("/")` and text to "Back to dashboard".

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/LaunchDetail.tsx frontend/src/pages/NarrativeDetail.tsx
git commit -m "fix: detail pages navigate back to unified dashboard"
```

---

### Task 4: Sync and Verify

- [ ] **Step 1: Copy all changed files to worktree** (if dev server runs from worktree)

```bash
for f in frontend/src/pages/UnifiedDashboard.tsx frontend/src/App.tsx frontend/src/pages/LaunchDetail.tsx frontend/src/pages/NarrativeDetail.tsx; do
  cp "$f" ".worktrees/pulse-redesign/$f" 2>/dev/null
done
```

- [ ] **Step 2: Verify frontend runs**

Open http://localhost:5173 — should show the unified dashboard.

- [ ] **Step 3: Verify detail routes work**

- Click a launch performance tier → should go to `/launch/peak-mcap`
- Click a narrative card → should go to `/narrative/AI` (or similar)
- Back buttons → should return to `/`

- [ ] **Step 4: Push**

```bash
git push origin feature/unified-dashboard
```
