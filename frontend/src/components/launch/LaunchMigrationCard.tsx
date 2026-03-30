import { useNavigate } from "react-router-dom";
import type { LaunchMetricData } from "../../types/launch";

function formatCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

const LP_LABELS: Record<string, string> = {
  pumpdotfun: "pump.fun",
  letsbonk: "LetsBonk",
  launchlab: "LaunchLab",
  bags: "Bags",
  moonshot: "Moonshot",
  boop: "Boop",
  believe: "Believe",
  jupstudio: "Jup Studio",
  wavebreak: "Wavebreak",
  sugar: "Sugar",
};

const BAR_COLORS = [
  "bg-terminal-accent",
  "bg-terminal-green",
  "bg-blue-400",
  "bg-purple-400",
  "bg-pink-400",
  "bg-cyan-400",
];

export default function LaunchMigrationCard({ metric }: { metric: LaunchMetricData }) {
  const navigate = useNavigate();
  const totalLaunches = metric.current ?? 0;
  const breakdown = metric.breakdown || {};
  const migrationRate = (metric as Record<string, unknown>).migration_rate as number | undefined;
  const totalGraduated = (metric as Record<string, unknown>).total_graduated as number | undefined;

  const sorted = Object.entries(breakdown)
    .filter(([, v]) => v != null && (v as number) > 0)
    .sort((a, b) => (b[1] as number) - (a[1] as number));

  const maxCount = sorted.length > 0 ? (sorted[0][1] as number) : 0;

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
        Token launches across all launchpads and graduation rate
      </div>

      {/* Main stats */}
      <div className="flex items-baseline gap-6 mb-4">
        <div>
          <div className="text-3xl font-bold text-terminal-text">{formatCount(totalLaunches)}</div>
          <div className="text-[11px] text-terminal-muted">launches</div>
        </div>
        {totalGraduated != null && totalGraduated > 0 && (
          <div>
            <div className="text-2xl font-bold text-terminal-green">{formatCount(totalGraduated)}</div>
            <div className="text-[11px] text-terminal-muted">graduated</div>
          </div>
        )}
        {migrationRate != null && migrationRate > 0 && (
          <div>
            <div className="text-2xl font-bold text-terminal-accent">{migrationRate.toFixed(1)}%</div>
            <div className="text-[11px] text-terminal-muted">grad rate</div>
          </div>
        )}
      </div>

      {/* Per-launchpad bars */}
      {sorted.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] text-terminal-muted/50 uppercase tracking-wider mb-1">
            By launchpad
          </div>
          {sorted.slice(0, 6).map(([lp, count], i) => {
            const pct = maxCount > 0 ? ((count as number) / maxCount) * 100 : 0;
            const label = LP_LABELS[lp] || lp;
            const barColor = BAR_COLORS[i % BAR_COLORS.length];

            return (
              <div key={lp} className="flex items-center gap-2">
                <div className="w-20 flex-shrink-0 text-xs text-terminal-text truncate">
                  {label}
                </div>
                <div className="flex-1 h-2 rounded-full bg-terminal-border/40 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${barColor} transition-all duration-500`}
                    style={{ width: `${Math.max(pct, 2)}%` }}
                  />
                </div>
                <div className="w-14 text-right text-[10px] tabular-nums text-terminal-muted">
                  {(count as number).toLocaleString()}
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
