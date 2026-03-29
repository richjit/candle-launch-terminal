import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import LaunchBreakdownTable from "../components/launch/LaunchBreakdownTable";
import { useApiPolling } from "../hooks/useApiPolling";
import type { LaunchMetricData, LaunchRange } from "../types/launch";

const RANGES: LaunchRange[] = ["7d", "30d", "90d"];

const METRIC_META: Record<string, { title: string; description: string; unit?: string }> = {
  "migration-rate": {
    title: "Migration Rate",
    description: "Percentage of tokens created on pump.fun that graduate to a DEX. Higher rates suggest stronger launch momentum.",
    unit: "%",
  },
  "peak-mcap": {
    title: "Launch Performance",
    description: "Peak market cap distribution for graduated tokens. Shows what to expect across different performance tiers if you launch now.",
    unit: "$",
  },
  "time-to-peak": {
    title: "Time to Peak",
    description: "How many minutes it takes for a new token to reach its peak price. Shorter times mean faster speculation cycles.",
    unit: "min",
  },
  survival: {
    title: "Survival Rate (24h)",
    description: "Percentage of launched tokens still actively trading after 24 hours. Low survival signals a rug-heavy environment.",
    unit: "%",
  },
  "buy-sell": {
    title: "Buy/Sell Ratio",
    description: "Ratio of buy transactions to sell transactions in the first hour. Above 1.0 means more buying than selling.",
  },
  launches: {
    title: "Launches (24h)",
    description: "Number of tokens that migrated from pump.fun to a DEX pool in the last 24 hours.",
  },
  volume: {
    title: "On-Chain DEX Volume",
    description: "Total trading volume across all Solana decentralized exchanges. Context for the overall market activity level.",
    unit: "$",
  },
};

function formatDetailValue(value: number, unit?: string): string {
  if (unit === "$") {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
    return `$${value.toFixed(0)}`;
  }
  if (unit === "%") return `${value.toFixed(2)}%`;
  if (unit === "min") return `${value.toFixed(0)} min`;
  return value.toLocaleString();
}

function AreaChart({ data }: { data: { date: string; value: number | null }[] }) {
  const entries = data.filter((d) => d.value !== null) as { date: string; value: number }[];
  if (entries.length < 2)
    return <div className="text-terminal-muted py-12 text-center text-sm">Not enough data yet</div>;

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

  // Y-axis labels
  const yTicks = 5;
  const yLabels = Array.from({ length: yTicks }, (_, i) => {
    const v = min + (range * i) / (yTicks - 1);
    const y = py + (1 - (v - min) / range) * (h - py * 2);
    return { v, y };
  });

  // X-axis labels (show ~5 dates)
  const step = Math.max(1, Math.floor(entries.length / 5));
  const xLabels = entries
    .filter((_, i) => i % step === 0 || i === entries.length - 1)
    .map((d, idx, arr) => ({
      label: new Date(d.date).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      x: px + ((entries.indexOf(d)) / (entries.length - 1)) * (w - px * 2),
    }));

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 320 }}>
      <defs>
        <linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f0b90b" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#f0b90b" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Grid lines */}
      {yLabels.map((t, i) => (
        <g key={i}>
          <line x1={px} y1={t.y} x2={w - px} y2={t.y} stroke="#1e1e2e" strokeWidth="1" />
          <text x={px - 8} y={t.y + 4} textAnchor="end" fill="#6b7280" fontSize="10" fontFamily="monospace">
            {t.v >= 1e9 ? `${(t.v / 1e9).toFixed(1)}B` : t.v >= 1e6 ? `${(t.v / 1e6).toFixed(0)}M` : t.v >= 1e3 ? `${(t.v / 1e3).toFixed(0)}K` : t.v.toFixed(1)}
          </text>
        </g>
      ))}

      {/* X labels */}
      {xLabels.map((t, i) => (
        <text key={i} x={t.x} y={h - 2} textAnchor="middle" fill="#6b7280" fontSize="10" fontFamily="monospace">
          {t.label}
        </text>
      ))}

      {/* Area + line */}
      <polygon points={area} fill="url(#chart-fill)" />
      <polyline points={line} fill="none" stroke="#f0b90b" strokeWidth={2} />

      {/* Current value dot */}
      {coords.length > 0 && (
        <circle
          cx={coords[coords.length - 1].x}
          cy={coords[coords.length - 1].y}
          r={4}
          fill="#f0b90b"
          stroke="#0a0a0f"
          strokeWidth={2}
        />
      )}
    </svg>
  );
}

export default function LaunchDetail() {
  const { metric } = useParams<{ metric: string }>();
  const navigate = useNavigate();
  const [range, setRange] = useState<LaunchRange>("30d");

  const { data, loading, error } = useApiPolling<LaunchMetricData>(
    `/launch/${metric}?range=${range}`,
    60000,
  );

  const meta = metric ? METRIC_META[metric] : undefined;
  const title = meta?.title || metric || "Metric";

  return (
    <PageLayout title={title}>
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => navigate("/launch")}
          className="text-sm text-terminal-muted hover:text-terminal-text transition-colors"
        >
          ← Back to monitor
        </button>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                range === r
                  ? "bg-terminal-accent/20 text-terminal-accent"
                  : "text-terminal-muted hover:text-terminal-text"
              }`}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {meta && (
        <p className="text-sm text-terminal-muted mb-5 max-w-2xl">{meta.description}</p>
      )}

      {data && (
        <>
          {/* Current value */}
          <div className="flex items-baseline gap-3 mb-6">
            <span className="text-4xl font-bold text-terminal-text tracking-tight">
              {data.current !== null ? formatDetailValue(data.current, meta?.unit) : "--"}
            </span>
            <span
              className={`text-sm font-medium ${
                data.trend === "up"
                  ? "text-terminal-green"
                  : data.trend === "down"
                    ? "text-terminal-red"
                    : "text-terminal-muted"
              }`}
            >
              {data.trend === "up" ? "▲ Trending up" : data.trend === "down" ? "▼ Trending down" : "— Stable"}
            </span>
          </div>

          {/* Chart */}
          <div className="bg-terminal-card border border-terminal-border rounded-lg p-5">
            <AreaChart data={data.chart} />
          </div>

          {/* Breakdown */}
          {data.breakdown && Object.keys(data.breakdown).length > 0 && (
            <div className="mt-6">
              <LaunchBreakdownTable breakdown={data.breakdown} />
            </div>
          )}
        </>
      )}

      {loading && !data && (
        <div className="text-terminal-muted text-center py-16">Loading...</div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}
    </PageLayout>
  );
}
