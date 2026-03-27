import type { EcosystemMetric } from "../../types/pulse";

interface EcosystemCardProps {
  metric: EcosystemMetric;
}

const MONETARY_METRICS = new Set(["stablecoin_supply"]);

function formatValue(value: number, name: string): string {
  if (MONETARY_METRICS.has(name)) {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    return `$${value.toLocaleString()}`;
  }
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toLocaleString();
}

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 60;
  const h = 20;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={w} height={h} className="inline-block">
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} />
    </svg>
  );
}

export default function EcosystemCard({ metric }: EcosystemCardProps) {
  const sparkColor = metric.direction === "up" ? "#00e676" : metric.direction === "down" ? "#ff1744" : "#6b7280";

  return (
    <div className="bg-terminal-card border border-terminal-border p-4">
      <div className="text-xs text-terminal-muted uppercase tracking-wider">{metric.label}</div>
      <div className="mt-1 flex items-center justify-between">
        <span className="text-xl font-bold text-terminal-text">
          {formatValue(metric.current, metric.name)}
        </span>
        {metric.sparkline.length > 1 && (
          <MiniSparkline data={metric.sparkline} color={sparkColor} />
        )}
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs">
        {metric.direction && (
          <span className={metric.direction === "up" ? "text-terminal-green" : "text-terminal-red"}>
            {metric.direction === "up" ? "▲" : "▼"}
          </span>
        )}
        {metric.sub_values && (
          <span className="text-terminal-muted">
            {Object.entries(metric.sub_values)
              .map(([k, v]) => `${k}: ${formatValue(v, k)}`)
              .join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}
