import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import LaunchBreakdownTable from "../components/launch/LaunchBreakdownTable";
import { useApiPolling } from "../hooks/useApiPolling";
import type { LaunchMetricData, LaunchRange } from "../types/launch";

const RANGES: LaunchRange[] = ["7d", "30d", "90d"];

const METRIC_TITLES: Record<string, string> = {
  "migration-rate": "Migration Rate",
  "peak-mcap": "Median Peak Market Cap",
  "time-to-peak": "Time to Peak",
  survival: "Survival Rate",
  "buy-sell": "Buy/Sell Ratio",
  launches: "Daily Launches",
  volume: "On-Chain Volume",
  "capital-flow": "Capital Flow",
};

function SimpleChart({ data }: { data: { date: string; value: number | null }[] }) {
  const values = data.map((d) => d.value).filter((v): v is number => v !== null);
  if (values.length < 2) return <div className="text-terminal-muted py-8 text-center">Insufficient data</div>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 800;
  const h = 300;
  const padding = 40;

  const points = data
    .map((d, i) => {
      if (d.value === null) return null;
      const x = padding + (i / (data.length - 1)) * (w - padding * 2);
      const y = padding + (1 - (d.value - min) / range) * (h - padding * 2);
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 300 }}>
      <polyline
        points={points}
        fill="none"
        stroke="var(--color-terminal-accent)"
        strokeWidth={2}
      />
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

  const title = metric ? METRIC_TITLES[metric] || metric : "Metric";

  return (
    <PageLayout title={title}>
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => navigate("/launch")}
          className="text-sm text-terminal-muted hover:text-terminal-text"
        >
          ← Back
        </button>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1 text-xs rounded ${
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

      {data && (
        <>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl font-bold text-terminal-text">
              {data.current !== null ? data.current.toLocaleString() : "—"}
            </span>
            <span
              className={`text-sm ${
                data.trend === "up"
                  ? "text-terminal-green"
                  : data.trend === "down"
                    ? "text-terminal-red"
                    : "text-terminal-muted"
              }`}
            >
              {data.trend === "up" ? "▲" : data.trend === "down" ? "▼" : "—"}
            </span>
          </div>

          <div className="bg-terminal-card border border-terminal-border rounded p-4">
            <SimpleChart data={data.chart} />
          </div>

          {data.breakdown && (
            <LaunchBreakdownTable breakdown={data.breakdown} />
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
