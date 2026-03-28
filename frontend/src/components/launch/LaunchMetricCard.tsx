import { useNavigate } from "react-router-dom";
import type { LaunchMetricData, LaunchMetricSlug } from "../../types/launch";

const METRIC_SLUGS: Record<string, LaunchMetricSlug> = {
  "Migration Rate": "migration-rate",
  "Median Peak Mcap (1h)": "peak-mcap",
  "Time to Peak": "time-to-peak",
  "Survival Rate (24h)": "survival",
  "Buy/Sell Ratio": "buy-sell",
  "Daily Launches": "launches",
  "Volume": "volume",
  "Capital Flow": "capital-flow",
};

function formatValue(name: string, value: number | null): string {
  if (value === null || value === undefined) return "—";
  if (name.includes("Rate") || name.includes("Migration")) return `${value.toFixed(1)}%`;
  if (name.includes("Mcap") || name.includes("Volume") || name.includes("Capital")) {
    if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
    return `$${value.toFixed(0)}`;
  }
  if (name.includes("Time")) return `${value.toFixed(0)}min`;
  if (name.includes("Ratio")) return value.toFixed(2);
  return value.toLocaleString();
}

function Sparkline({ data }: { data: { value: number | null }[] }) {
  const values = data.map((d) => d.value).filter((v): v is number => v !== null);
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 120;
  const h = 32;

  const points = values
    .slice(-30)
    .map((v, i, arr) => {
      const x = (i / (arr.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={w} height={h} className="mt-2">
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        className="text-terminal-accent"
      />
    </svg>
  );
}

const TREND_ARROWS = { up: "▲", down: "▼", flat: "—" };
const TREND_COLORS = {
  up: "text-terminal-green",
  down: "text-terminal-red",
  flat: "text-terminal-muted",
};

export default function LaunchMetricCard({ metric }: { metric: LaunchMetricData }) {
  const navigate = useNavigate();
  const slug = METRIC_SLUGS[metric.name];

  return (
    <button
      onClick={() => slug && navigate(`/launch/${slug}`)}
      className="bg-terminal-card border border-terminal-border rounded p-4 text-left hover:border-terminal-accent/40 transition-colors w-full"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs text-terminal-muted uppercase tracking-wide">
          {metric.name}
        </span>
        <span className={`text-xs ${TREND_COLORS[metric.trend]}`}>
          {TREND_ARROWS[metric.trend]}
        </span>
      </div>
      <div className="text-xl font-bold text-terminal-text mt-1">
        {metric.current !== null ? formatValue(metric.name, metric.current) : (
          <span className="text-terminal-muted text-sm">Collecting data...</span>
        )}
      </div>
      <Sparkline data={metric.chart} />
    </button>
  );
}
