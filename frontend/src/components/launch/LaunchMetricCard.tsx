import { useNavigate } from "react-router-dom";
import type { LaunchMetricData, LaunchMetricSlug } from "../../types/launch";

const METRIC_SLUGS: Record<string, LaunchMetricSlug> = {
  "Migration Rate": "migration-rate",
  "Launch Performance": "peak-mcap",
  "Survival Rate (24h)": "survival",
  "Buy/Sell Ratio": "buy-sell",
  "Daily Launches": "launches",
  "Volume": "volume",
};

const METRIC_DESCRIPTIONS: Record<string, string> = {
  "Migration Rate": "Tokens graduating to DEX vs total created",
  "Launch Performance": "Peak mcap distribution for graduated tokens",
  "Survival Rate (24h)": "Tokens still actively trading after 24 hours",
  "Buy/Sell Ratio": "Buy pressure vs sell pressure in first hour",
  "Daily Launches": "Tokens migrated to DEX in the last 24h",
  "Volume": "Total Solana DEX trading volume",
};

const METRIC_TIMEFRAMES: Record<string, string> = {
  "Migration Rate": "24h",
  "Launch Performance": "24h",
  "Survival Rate (24h)": "24h",
  "Buy/Sell Ratio": "24h",
  "Daily Launches": "24h",
  "Volume": "24h",
};

type HealthLevel = "good" | "neutral" | "bad";

function getHealth(name: string, value: number | null): HealthLevel {
  if (value === null) return "neutral";
  if (name.includes("Migration")) return value > 1.5 ? "good" : value < 0.5 ? "bad" : "neutral";
  if (name.includes("Survival")) return value > 50 ? "good" : value < 30 ? "bad" : "neutral";
  if (name.includes("Ratio")) return value > 1.0 ? "good" : value < 0.5 ? "bad" : "neutral";
  if (name.includes("Peak Mcap")) return value > 5000 ? "good" : value < 1000 ? "bad" : "neutral";
  if (name.includes("Launches")) return value > 200 ? "good" : value < 50 ? "bad" : "neutral";
  return "neutral";
}

const HEALTH_COLORS: Record<HealthLevel, string> = {
  good: "bg-terminal-green",
  neutral: "bg-terminal-accent",
  bad: "bg-terminal-red",
};

const HEALTH_GLOW: Record<HealthLevel, string> = {
  good: "shadow-[0_0_6px_rgba(0,230,118,0.3)]",
  neutral: "shadow-[0_0_6px_rgba(240,185,11,0.3)]",
  bad: "shadow-[0_0_6px_rgba(255,23,68,0.3)]",
};

function formatValue(name: string, value: number | null): string {
  if (value === null || value === undefined) return "--";
  if (name.includes("Rate") || name.includes("Migration")) return `${value.toFixed(1)}%`;
  if (name.includes("Mcap") || name.includes("Volume")) {
    if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
    if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
    return `$${value.toFixed(0)}`;
  }
  if (name.includes("Time")) return `${value.toFixed(0)} min`;
  if (name.includes("Ratio")) return value.toFixed(2);
  return value.toLocaleString();
}

function Sparkline({ data, health }: { data: { value: number | null }[]; health: HealthLevel }) {
  const values = data.map((d) => d.value).filter((v): v is number => v !== null);
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 200;
  const h = 48;

  const pointCoords = values.slice(-30).map((v, i, arr) => ({
    x: (i / (arr.length - 1)) * w,
    y: h - ((v - min) / range) * (h - 4) - 2,
  }));

  const line = pointCoords.map((p) => `${p.x},${p.y}`).join(" ");
  // Area fill: line + bottom corners
  const area = `${line} ${w},${h} 0,${h}`;

  const strokeColor =
    health === "good" ? "#00e676" : health === "bad" ? "#ff1744" : "#f0b90b";
  const fillId = `grad-${health}`;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="mt-3">
      <defs>
        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.15" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${fillId})`} />
      <polyline points={line} fill="none" stroke={strokeColor} strokeWidth={1.5} />
    </svg>
  );
}

const TREND_LABELS = { up: "Trending up", down: "Trending down", flat: "Stable" };
const TREND_COLORS = {
  up: "text-terminal-green",
  down: "text-terminal-red",
  flat: "text-terminal-muted",
};

export default function LaunchMetricCard({ metric }: { metric: LaunchMetricData }) {
  const navigate = useNavigate();
  const slug = METRIC_SLUGS[metric.name];
  const health = getHealth(metric.name, metric.current);
  const description = METRIC_DESCRIPTIONS[metric.name] || "";
  const timeframe = METRIC_TIMEFRAMES[metric.name];

  return (
    <button
      onClick={() => slug && navigate(`/launch/${slug}`)}
      className="bg-terminal-card border border-terminal-border rounded-lg p-5 text-left hover:border-terminal-accent/40 transition-all w-full group"
    >
      {/* Header: indicator dot + name + timeframe */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full ${HEALTH_COLORS[health]} ${HEALTH_GLOW[health]}`} />
          <span className="text-xs text-terminal-muted uppercase tracking-wider font-medium">
            {metric.name}
          </span>
        </div>
        {timeframe && (
          <span className="text-[10px] text-terminal-muted/40">{timeframe}</span>
        )}
      </div>

      {/* Description */}
      <div className="text-[11px] text-terminal-muted/60 mb-3 leading-tight">
        {description}
      </div>

      {/* Value */}
      <div className="text-2xl font-bold text-terminal-text tracking-tight">
        {metric.current !== null ? formatValue(metric.name, metric.current) : (
          <span className="text-terminal-muted text-sm font-normal">Awaiting data...</span>
        )}
      </div>

      {/* Trend */}
      <div className="mt-1">
        <span className={`text-[11px] ${TREND_COLORS[metric.trend]}`}>
          {TREND_LABELS[metric.trend]}
        </span>
      </div>

      {/* Breakdown bars */}
      {metric.breakdown && Object.keys(metric.breakdown).length > 1 && (
        <div className="mt-3 space-y-1.5">
          {Object.entries(metric.breakdown)
            .filter(([, v]) => v != null && v > 0)
            .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
            .slice(0, 5)
            .map(([k, v]) => {
              const max = Math.max(...Object.values(metric.breakdown!).filter((x): x is number => x != null));
              const pct = max > 0 ? ((v ?? 0) / max) * 100 : 0;
              return (
                <div key={k} className="flex items-center gap-2">
                  <span className="text-[10px] text-terminal-muted w-20 truncate">{k}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-terminal-border/30 overflow-hidden">
                    <div className="h-full rounded-full bg-terminal-accent/60" style={{ width: `${Math.max(pct, 2)}%` }} />
                  </div>
                  <span className="text-[10px] tabular-nums text-terminal-muted w-12 text-right">
                    {(v ?? 0).toLocaleString()}
                  </span>
                </div>
              );
            })}
        </div>
      )}

      {/* Sparkline */}
      <Sparkline data={metric.chart} health={health} />

      {/* Hover hint */}
      <div className="text-[10px] text-terminal-muted/0 group-hover:text-terminal-muted/40 transition-colors mt-2 text-right">
        View details →
      </div>
    </button>
  );
}
