import { useNavigate } from "react-router-dom";
import type { LaunchMetricData } from "../../types/launch";

function formatMcap(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
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

const TIER_CONFIG = [
  {
    key: "best24h" as const,
    label: "Best (24h)",
    description: "Top performer in the last 24 hours",
    color: "text-terminal-accent",
    dotColor: "bg-terminal-accent shadow-[0_0_6px_rgba(240,185,11,0.4)]",
  },
  {
    key: "top10" as const,
    label: "Top 10%",
    description: "Tokens that got some traction",
    color: "text-blue-400",
    dotColor: "bg-blue-400 shadow-[0_0_6px_rgba(96,165,250,0.4)]",
  },
  {
    key: "bonded" as const,
    label: "Bonded",
    description: "Median peak for graduated tokens",
    color: "text-terminal-text",
    dotColor: "bg-terminal-text/60",
  },
];

function TierBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.max(2, (Math.log10(value + 1) / Math.log10(max + 1)) * 100) : 0;
  return (
    <div className="h-1.5 rounded-full bg-terminal-border/40 overflow-hidden w-full">
      <div
        className="h-full rounded-full bg-current transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default function LaunchPerformanceCard({ metric }: { metric: LaunchMetricData }) {
  const navigate = useNavigate();
  const tiers = metric.tiers;

  if (!tiers) {
    return (
      <button
        onClick={() => navigate("/launch/peak-mcap")}
        className="bg-terminal-card border border-terminal-border rounded-lg p-5 text-left hover:border-terminal-accent/40 transition-all w-full col-span-1 sm:col-span-2"
      >
        <div className="text-xs text-terminal-muted uppercase tracking-wider font-medium mb-2">
          Launch Performance
        </div>
        <div className="text-terminal-muted text-sm">Collecting data...</div>
      </button>
    );
  }

  const dexScreenerUrl = tiers.best_address
    ? `https://dexscreener.com/solana/${tiers.best_address}`
    : null;

  return (
    <div
      onClick={() => navigate("/launch/peak-mcap")}
      className="bg-terminal-card border border-terminal-border rounded-lg p-5 text-left hover:border-terminal-accent/40 transition-all w-full col-span-1 sm:col-span-2 group cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-terminal-accent shadow-[0_0_6px_rgba(240,185,11,0.3)]" />
          <span className="text-xs text-terminal-muted uppercase tracking-wider font-medium">
            Launch Performance
          </span>
        </div>
        <span className="text-[10px] text-terminal-muted/40">
          {tiers.sample_size} tokens · 24h
        </span>
      </div>

      <div className="text-[11px] text-terminal-muted/60 mb-4 leading-tight">
        Peak market cap distribution for graduated tokens in the last 24h
      </div>

      {/* Column headers */}
      <div className="flex items-center gap-3 mb-2">
        <div className="w-2 flex-shrink-0" />
        <div className="w-28 flex-shrink-0" />
        <div className="flex-1 text-[10px] text-terminal-muted/40 uppercase tracking-wider">Peak Mcap</div>
        <div className="w-20 text-right text-[10px] text-terminal-muted/40 uppercase tracking-wider">Mcap</div>
        <div className="w-14 text-right text-[10px] text-terminal-muted/40 uppercase tracking-wider">Reached after</div>
      </div>

      {/* Tiers */}
      <div className="space-y-3">
        {TIER_CONFIG.map((tier) => {
          const value = tiers[tier.key];
          const ttp = tiers.time_to_peak?.[tier.key];
          return (
            <div key={tier.key}>
              <div className="flex items-center gap-3">
                {/* Dot */}
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${tier.dotColor}`} />

                {/* Label + description */}
                <div className="w-28 flex-shrink-0">
                  <div className={`text-xs font-medium ${tier.color}`}>{tier.label}</div>
                  <div className="text-[10px] text-terminal-muted/50 leading-tight">
                    {tier.description}
                  </div>
                </div>

                {/* Bar */}
                <div className={`flex-1 ${tier.color}`}>
                  <TierBar value={value} max={tiers.best24h} />
                </div>

                {/* Peak Mcap */}
                <div className={`text-sm font-bold tabular-nums text-right w-20 flex-shrink-0 ${tier.color}`}>
                  {formatMcap(value)}
                </div>

                {/* Time to Peak */}
                <div className="text-xs tabular-nums text-right w-14 flex-shrink-0 text-terminal-muted">
                  {formatTime(ttp)}
                </div>
              </div>

              {/* Best performer details — shown under the best24h tier */}
              {tier.key === "best24h" && tiers.best_address && (
                <div className="ml-5 mt-1.5 flex items-center gap-2 text-[10px]">
                  <span className="text-terminal-muted/60 font-mono">
                    CA: {truncateAddress(tiers.best_address)}
                  </span>
                  {dexScreenerUrl && (
                    <a
                      href={dexScreenerUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-terminal-accent/70 hover:text-terminal-accent transition-colors underline underline-offset-2"
                    >
                      DexScreener
                    </a>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* All launches (including unbonded) */}
      {tiers.all_median != null && (
        <div className="mt-4 pt-3 border-t border-terminal-border/30">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full flex-shrink-0 bg-terminal-red/50 shadow-[0_0_6px_rgba(255,23,68,0.2)]" />
            <div className="w-28 flex-shrink-0">
              <div className="text-xs font-medium text-terminal-red/70">All Launches</div>
              <div className="text-[10px] text-terminal-muted/50 leading-tight">
                Median including unbonded
              </div>
            </div>
            <div className="flex-1 text-terminal-red/70">
              <TierBar value={tiers.all_median} max={tiers.best24h} />
            </div>
            <div className="text-sm font-bold tabular-nums text-right w-20 flex-shrink-0 text-terminal-red/70">
              {formatMcap(tiers.all_median)}
            </div>
          </div>
        </div>
      )}

      {/* Footer hint */}
      <div className="text-[10px] text-terminal-muted/0 group-hover:text-terminal-muted/40 transition-colors mt-3 text-right">
        View details →
      </div>
    </div>
  );
}
