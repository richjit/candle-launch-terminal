import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import CandlestickChart, { type CandlestickChartHandle } from "../components/charts/CandlestickChart";
import LaunchPerformanceCard from "../components/launch/LaunchPerformanceCard";
import LaunchMigrationCard from "../components/launch/LaunchMigrationCard";
import LaunchMetricCard from "../components/launch/LaunchMetricCard";
import { useApiPolling } from "../hooks/useApiPolling";
import { fetchChart } from "../api/pulse";
import type { ChartData } from "../types/pulse";
import type { LaunchOverviewData } from "../types/launch";
import type { NarrativeOverview, NarrativeData, NarrativeTokenData } from "../types/narrative";

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

export default function UnifiedDashboard() {
  const navigate = useNavigate();
  const chartRef = useRef<CandlestickChartHandle>(null);
  const initialRangeSet = useRef(false);

  const [chartData, setChartData] = useState<ChartData | null>(null);
  const { data: launchData } = useApiPolling<LaunchOverviewData>("/launch/overview?range=30d", 60000);
  const { data: narrativeData } = useApiPolling<NarrativeOverview>("/narrative/overview", 60000);

  useEffect(() => {
    const defaultExcluded = ["dex_volume", "stablecoin_supply", "vol_regime", "new_wallets", "priority_fees"];
    fetchChart("all", defaultExcluded).then(setChartData).catch(() => {});
    const interval = setInterval(() => {
      fetchChart("all", defaultExcluded).then(setChartData).catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // Set 90d range only on first load — don't reset when polling refreshes data
  useEffect(() => {
    if (!chartData || initialRangeSet.current) return;
    const timer = setTimeout(() => {
      const chart = chartRef.current?.getChart();
      if (chart) {
        const now = Math.floor(Date.now() / 1000);
        chart.timeScale().setVisibleRange({ from: (now - 90 * 86400) as any, to: now as any });
        initialRangeSet.current = true;
      }
    }, 50);
    return () => clearTimeout(timer);
  }, [chartData]);

  const currentScore = chartData?.scores?.length
    ? chartData.scores[chartData.scores.length - 1].score
    : null;

  const activity = launchData?.metrics.find((m) => m.name === "Launchpad Activity");
  const launchCount = activity?.current ?? 0;
  const migrationRate = (activity as Record<string, unknown> | undefined)?.migration_rate as number | undefined;
  const survivalMetric = launchData?.metrics.find((m) => m.name === "Survival Rate (24h)");

  return (
    <div className="max-w-7xl mx-auto">
      {/* Tier 1: Hero */}
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

        {chartData && chartData.candles.length > 0 && (
          <CandlestickChart ref={chartRef} candles={chartData.candles} scores={chartData.scores} height={200} />
        )}
      </div>

      {/* Tier 2: Launch Conditions */}
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

      {/* Tier 3: What to Launch */}
      <div>
        <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">Trending Narratives</div>

        <div className="bg-terminal-red/5 border border-terminal-red/20 rounded-lg px-4 py-3 mb-4">
          <p className="text-xs text-terminal-red/80 leading-relaxed">
            This tool identifies trending narratives for token developers. Tokens shown here include
            unverified and potentially dangerous coins. This is not investment advice — do not buy
            tokens based on this data.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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
