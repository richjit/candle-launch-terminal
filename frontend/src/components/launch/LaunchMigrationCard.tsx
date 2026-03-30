import { useNavigate } from "react-router-dom";
import type { LaunchMetricData } from "../../types/launch";

function formatPct(value: number): string {
  if (value < 0.01) return "<0.01%";
  if (value < 1) return `${value.toFixed(2)}%`;
  return `${value.toFixed(1)}%`;
}

function formatCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

const LP_LABELS: Record<string, string> = {
  pumpfun: "pump.fun",
  launchlab: "LaunchLab",
  meteora: "Meteora",
  bonk: "Bonk",
  bags: "Bags",
  candle: "Candle",
  moonshot: "Moonshot",
};

const LP_COLORS = [
  "bg-terminal-accent",
  "bg-terminal-green",
  "bg-blue-400",
  "bg-purple-400",
  "bg-pink-400",
];

export default function LaunchMigrationCard({ metric }: { metric: LaunchMetricData }) {
  const navigate = useNavigate();
  const rate = metric.current;
  const breakdown = metric.breakdown || {};
  const totalGraduated = (metric as Record<string, unknown>).total_graduated as number | undefined;
  const totalLaunches = (metric as Record<string, unknown>).total_launches as number | undefined;

  // Breakdown can be either {platform: count} or {platform: {creates, graduated, rate}}
  const isRichBreakdown = Object.values(breakdown).some(
    (v) => v != null && typeof v === "object"
  );

  type PlatformData = { creates: number; graduated: number; rate: number };
  const platforms: [string, PlatformData][] = isRichBreakdown
    ? Object.entries(breakdown)
        .filter(([, v]) => v != null && typeof v === "object")
        .map(([k, v]) => [k, v as unknown as PlatformData])
        .sort((a, b) => b[1].creates - a[1].creates)
    : Object.entries(breakdown)
        .filter(([, v]) => v != null && (v as number) > 0)
        .sort((a, b) => (b[1] as number) - (a[1] as number))
        .map(([k, v]) => [k, { creates: v as number, graduated: 0, rate: 0 }]);

  const maxCreates = platforms.length > 0 ? platforms[0][1].creates : 0;

  return (
    <div
      onClick={() => navigate("/launch/migration-rate")}
      className="bg-terminal-card border border-terminal-border rounded-lg p-5 text-left hover:border-terminal-accent/40 transition-all w-full col-span-1 sm:col-span-2 group cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-terminal-accent shadow-[0_0_6px_rgba(240,185,11,0.3)]" />
          <span className="text-xs text-terminal-muted uppercase tracking-wider font-medium">
            Launchpad Activity
          </span>
        </div>
        <span className="text-[10px] text-terminal-muted/40">24h</span>
      </div>

      <div className="text-[11px] text-terminal-muted/60 mb-4 leading-tight">
        Tokens graduating from bonding curve to DEX in the last 24h
      </div>

      {/* Main rate + counts */}
      <div className="flex items-baseline gap-3 mb-4">
        <span className="text-3xl font-bold text-terminal-text">
          {rate != null ? formatPct(rate) : "--"}
        </span>
        {totalGraduated != null && totalLaunches != null && (
          <span className="text-sm text-terminal-muted">
            {formatCount(totalGraduated)} graduated / {formatCount(totalLaunches)} created
          </span>
        )}
      </div>

      {/* Per-launchpad table */}
      {platforms.length > 0 && (
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-[10px] text-terminal-muted/50 uppercase tracking-wider mb-2">
            <span className="w-20">Platform</span>
            <span className="flex-1">Creates</span>
            <span className="w-14 text-right">Grads</span>
            <span className="w-12 text-right">Rate</span>
          </div>
          {platforms.slice(0, 6).map(([lp, data], i) => {
            const pct = maxCreates > 0 ? (data.creates / maxCreates) * 100 : 0;
            const label = LP_LABELS[lp] || lp;
            const barColor = LP_COLORS[i % LP_COLORS.length];

            return (
              <div key={lp} className="flex items-center gap-2">
                <div className="w-20 flex-shrink-0 text-xs text-terminal-text truncate">
                  {label}
                </div>
                <div className="flex-1 flex items-center gap-2">
                  <div className="flex-1 h-2 rounded-full bg-terminal-border/40 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${barColor} transition-all duration-500`}
                      style={{ width: `${Math.max(pct, 2)}%` }}
                    />
                  </div>
                  <span className="text-[10px] tabular-nums text-terminal-muted w-12 text-right">
                    {data.creates.toLocaleString()}
                  </span>
                </div>
                <div className="w-14 text-right text-[10px] tabular-nums text-terminal-green">
                  {data.graduated > 0 ? data.graduated.toLocaleString() : "--"}
                </div>
                <div className="w-12 text-right text-[10px] tabular-nums text-terminal-muted">
                  {data.rate > 0 ? `${data.rate}%` : "--"}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      <div className="text-[10px] text-terminal-muted/0 group-hover:text-terminal-muted/40 transition-colors mt-3 text-right">
        View details →
      </div>
    </div>
  );
}
