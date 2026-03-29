import { useParams, useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import LaunchBreakdownTable from "../components/launch/LaunchBreakdownTable";
import { useApiPolling } from "../hooks/useApiPolling";
import type { LaunchOverviewData, LaunchMetricData } from "../types/launch";

const SLUG_TO_NAME: Record<string, string> = {
  "migration-rate": "Migration Rate",
  "peak-mcap": "Launch Performance",
  survival: "Survival Rate (24h)",
  "buy-sell": "Buy/Sell Ratio",
  launches: "Daily Launches",
  volume: "Volume",
};

const METRIC_META: Record<string, { title: string; description: string; unit?: string }> = {
  "migration-rate": {
    title: "Migration Rate",
    description:
      "Percentage of all tokens created on Solana that graduate from a bonding curve to a real DEX. This measures overall launch-to-graduation conversion across all launchpads.",
    unit: "%",
  },
  "peak-mcap": {
    title: "Launch Performance",
    description:
      "Peak market cap distribution for graduated tokens in the last 24 hours. Shows what different tiers of launches achieve and how long they take to reach their peak.",
    unit: "$",
  },
  survival: {
    title: "Survival Rate",
    description:
      "Percentage of tokens launched in the last 24 hours that are still actively trading (volume > $100/hr). Low survival signals a rug-heavy or low-attention environment.",
    unit: "%",
  },
  "buy-sell": {
    title: "Buy/Sell Ratio",
    description:
      "Average ratio of buy transactions to sell transactions in the first hour after launch. Above 1.0 means more buying than selling — bullish sentiment for new launches.",
  },
  launches: {
    title: "Launches",
    description:
      "Total number of new tokens created on Solana in the last 24 hours, sourced from on-chain data via Dune Analytics.",
  },
  volume: {
    title: "DEX Volume",
    description:
      "Total trading volume across all Solana decentralized exchanges. Provides context for overall market activity and liquidity conditions.",
    unit: "$",
  },
};

function formatValue(value: number | null, unit?: string): string {
  if (value == null) return "--";
  if (unit === "$") {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
    return `$${value.toFixed(0)}`;
  }
  if (unit === "%") return `${value.toFixed(2)}%`;
  return value.toLocaleString();
}

function formatMcap(value: number): string {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

function formatTime(minutes: number | null): string {
  if (minutes == null) return "--";
  if (minutes < 1) return "<1m";
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const h = Math.floor(minutes / 60);
  if (h >= 24) {
    const d = Math.floor(h / 24);
    const rh = h % 24;
    return rh > 0 ? `${d}d ${rh}h` : `${d}d`;
  }
  const m = Math.round(minutes % 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function truncateAddress(addr: string): string {
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

const LP_LABELS: Record<string, string> = {
  pumpfun: "pump.fun",
  launchlab: "LaunchLab",
  meteora: "Meteora",
  bonk: "Bonk",
  bags: "Bags",
  candle: "Candle",
};

// ── Detail sections per metric ──────────────────────────────────────

function PerformanceDetail({ metric }: { metric: LaunchMetricData }) {
  const tiers = metric.tiers;
  if (!tiers) return <div className="text-terminal-muted">Collecting data...</div>;

  const ttp = tiers.time_to_peak;
  const tierRows = [
    { key: "best24h", label: "Best (24h)", color: "text-terminal-accent" },
    { key: "top1", label: "Top 1%", color: "text-terminal-green" },
    { key: "top10", label: "Top 10%", color: "text-blue-400" },
    { key: "bonded", label: "Bonded (median)", color: "text-terminal-text" },
  ] as const;

  return (
    <div className="space-y-6">
      <div className="bg-terminal-card border border-terminal-border rounded-lg p-5">
        <div className="text-xs text-terminal-muted uppercase tracking-wider mb-4">
          Performance Tiers — {tiers.sample_size} graduated tokens (24h)
        </div>
        <table className="w-full">
          <thead>
            <tr className="text-[11px] text-terminal-muted/50 uppercase tracking-wider">
              <th className="text-left pb-3 font-medium">Tier</th>
              <th className="text-right pb-3 font-medium">Peak Mcap</th>
              <th className="text-right pb-3 font-medium">Time to Peak</th>
            </tr>
          </thead>
          <tbody>
            {tierRows.map((t) => (
              <tr key={t.key} className="border-t border-terminal-border/20">
                <td className={`py-3 text-sm font-medium ${t.color}`}>{t.label}</td>
                <td className={`py-3 text-sm font-bold text-right tabular-nums ${t.color}`}>
                  {formatMcap(tiers[t.key])}
                </td>
                <td className="py-3 text-sm text-right tabular-nums text-terminal-muted">
                  {formatTime(ttp?.[t.key] ?? null)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {tiers.all_median != null && (
          <div className="mt-4 pt-3 border-t border-terminal-border/30 flex justify-between text-sm">
            <span className="text-terminal-red/70">All Launches (median)</span>
            <span className="text-terminal-red/70 font-bold tabular-nums">
              {formatMcap(tiers.all_median)}
              <span className="font-normal text-terminal-muted ml-2">
                ({tiers.all_count?.toLocaleString()} tokens)
              </span>
            </span>
          </div>
        )}
      </div>

      {tiers.best_address && (
        <div className="bg-terminal-card border border-terminal-border rounded-lg p-5">
          <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">
            Best Performer (24h)
          </div>
          <div className="flex items-center gap-4">
            <span className="text-2xl font-bold text-terminal-accent">{formatMcap(tiers.best24h)}</span>
            <div className="text-sm">
              <div className="font-mono text-terminal-muted">{truncateAddress(tiers.best_address)}</div>
              <a
                href={`https://dexscreener.com/solana/${tiers.best_address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-terminal-accent/70 hover:text-terminal-accent text-xs underline underline-offset-2"
              >
                View on DexScreener
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MigrationDetail({ metric }: { metric: LaunchMetricData }) {
  const breakdown = metric.breakdown || {};
  const totalGraduated = (metric as Record<string, unknown>).total_graduated as number | undefined;
  const totalLaunches = (metric as Record<string, unknown>).total_launches as number | undefined;

  const sorted = Object.entries(breakdown)
    .filter(([, v]) => v != null && v > 0)
    .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));

  return (
    <div className="space-y-6">
      <div className="bg-terminal-card border border-terminal-border rounded-lg p-5">
        <div className="grid grid-cols-3 gap-6">
          <div>
            <div className="text-xs text-terminal-muted uppercase tracking-wider mb-1">Rate</div>
            <div className="text-3xl font-bold text-terminal-text">
              {metric.current != null ? `${metric.current.toFixed(2)}%` : "--"}
            </div>
          </div>
          <div>
            <div className="text-xs text-terminal-muted uppercase tracking-wider mb-1">Graduated</div>
            <div className="text-3xl font-bold text-terminal-green">{totalGraduated?.toLocaleString() ?? "--"}</div>
          </div>
          <div>
            <div className="text-xs text-terminal-muted uppercase tracking-wider mb-1">Total Created</div>
            <div className="text-3xl font-bold text-terminal-muted">{totalLaunches?.toLocaleString() ?? "--"}</div>
          </div>
        </div>
      </div>

      {sorted.length > 0 && (
        <div className="bg-terminal-card border border-terminal-border rounded-lg p-5">
          <div className="text-xs text-terminal-muted uppercase tracking-wider mb-4">By Launchpad</div>
          <div className="space-y-3">
            {sorted.map(([lp, count]) => {
              const pct = totalGraduated ? ((count ?? 0) / totalGraduated * 100) : 0;
              return (
                <div key={lp} className="flex items-center gap-4">
                  <div className="w-24 text-sm text-terminal-text font-medium">
                    {LP_LABELS[lp] || lp}
                  </div>
                  <div className="flex-1 h-3 rounded-full bg-terminal-border/40 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-terminal-accent transition-all"
                      style={{ width: `${Math.max(pct, 1)}%` }}
                    />
                  </div>
                  <div className="w-20 text-right text-sm tabular-nums text-terminal-muted">
                    {(count ?? 0).toLocaleString()}
                  </div>
                  <div className="w-16 text-right text-xs tabular-nums text-terminal-muted/50">
                    {pct.toFixed(1)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function SimpleMetricDetail({ metric, unit }: { metric: LaunchMetricData; unit?: string }) {
  return (
    <div className="space-y-6">
      <div className="bg-terminal-card border border-terminal-border rounded-lg p-5">
        <div className="flex items-baseline gap-3">
          <span className="text-4xl font-bold text-terminal-text">
            {formatValue(metric.current, unit)}
          </span>
          <span className={`text-sm ${
            metric.trend === "up" ? "text-terminal-green" :
            metric.trend === "down" ? "text-terminal-red" : "text-terminal-muted"
          }`}>
            {metric.trend === "up" ? "Trending up" : metric.trend === "down" ? "Trending down" : "Stable"}
          </span>
        </div>
      </div>

      {metric.chart.length > 1 && (
        <div className="bg-terminal-card border border-terminal-border rounded-lg p-5">
          <AreaChart data={metric.chart} />
        </div>
      )}

      {metric.breakdown && Object.keys(metric.breakdown).length > 0 && (
        <div className="bg-terminal-card border border-terminal-border rounded-lg p-5">
          <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">Breakdown</div>
          <LaunchBreakdownTable breakdown={metric.breakdown} />
        </div>
      )}
    </div>
  );
}

function AreaChart({ data }: { data: { date: string; value: number | null }[] }) {
  const entries = data.filter((d) => d.value !== null) as { date: string; value: number }[];
  if (entries.length < 2)
    return <div className="text-terminal-muted py-12 text-center text-sm">Not enough chart data yet</div>;

  const values = entries.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 800;
  const h = 280;
  const px = 50;
  const py = 20;

  const coords = entries.map((d, i) => ({
    x: px + (i / (entries.length - 1)) * (w - px * 2),
    y: py + (1 - (d.value - min) / range) * (h - py * 2),
  }));

  const line = coords.map((c) => `${c.x},${c.y}`).join(" ");
  const area = `${px},${h - py} ${line} ${w - px},${h - py}`;

  const yTicks = 5;
  const yLabels = Array.from({ length: yTicks }, (_, i) => {
    const v = min + (range * i) / (yTicks - 1);
    const y = py + (1 - (v - min) / range) * (h - py * 2);
    return { v, y };
  });

  const step = Math.max(1, Math.floor(entries.length / 5));
  const xLabels = entries
    .filter((_, i) => i % step === 0 || i === entries.length - 1)
    .map((d) => ({
      label: new Date(d.date).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      x: px + (entries.indexOf(d) / (entries.length - 1)) * (w - px * 2),
    }));

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 320 }}>
      <defs>
        <linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f0b90b" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#f0b90b" stopOpacity="0" />
        </linearGradient>
      </defs>
      {yLabels.map((t, i) => (
        <g key={i}>
          <line x1={px} y1={t.y} x2={w - px} y2={t.y} stroke="#1e1e2e" strokeWidth="1" />
          <text x={px - 8} y={t.y + 4} textAnchor="end" fill="#6b7280" fontSize="10" fontFamily="monospace">
            {t.v >= 1e9 ? `${(t.v / 1e9).toFixed(1)}B` : t.v >= 1e6 ? `${(t.v / 1e6).toFixed(0)}M` : t.v >= 1e3 ? `${(t.v / 1e3).toFixed(0)}K` : t.v.toFixed(1)}
          </text>
        </g>
      ))}
      {xLabels.map((t, i) => (
        <text key={i} x={t.x} y={h - 2} textAnchor="middle" fill="#6b7280" fontSize="10" fontFamily="monospace">
          {t.label}
        </text>
      ))}
      <polygon points={area} fill="url(#chart-fill)" />
      <polyline points={line} fill="none" stroke="#f0b90b" strokeWidth={2} />
      {coords.length > 0 && (
        <circle cx={coords[coords.length - 1].x} cy={coords[coords.length - 1].y} r={4} fill="#f0b90b" stroke="#0a0a0f" strokeWidth={2} />
      )}
    </svg>
  );
}

// ── Main component ──────────────────────────────────────────────────

export default function LaunchDetail() {
  const { metric: slug } = useParams<{ metric: string }>();
  const navigate = useNavigate();

  const { data, loading, error } = useApiPolling<LaunchOverviewData>(
    `/launch/overview?range=30d`,
    60000,
  );

  const meta = slug ? METRIC_META[slug] : undefined;
  const title = meta?.title || slug || "Metric";
  const metricName = slug ? SLUG_TO_NAME[slug] : undefined;
  const metric = data?.metrics.find((m) => m.name === metricName);

  return (
    <PageLayout title={title}>
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => navigate("/launch")}
          className="text-sm text-terminal-muted hover:text-terminal-text transition-colors"
        >
          ← Back to monitor
        </button>
        <span className="text-[10px] text-terminal-muted/40">24h</span>
      </div>

      {meta && (
        <p className="text-sm text-terminal-muted mb-6 max-w-2xl leading-relaxed">{meta.description}</p>
      )}

      {loading && !data && (
        <div className="text-terminal-muted text-center py-16">Loading...</div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}

      {metric && slug === "peak-mcap" && <PerformanceDetail metric={metric} />}
      {metric && slug === "migration-rate" && <MigrationDetail metric={metric} />}
      {metric && slug !== "peak-mcap" && slug !== "migration-rate" && (
        <SimpleMetricDetail metric={metric} unit={meta?.unit} />
      )}
    </PageLayout>
  );
}
