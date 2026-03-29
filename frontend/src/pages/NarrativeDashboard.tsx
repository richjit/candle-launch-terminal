import { useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import { useApiPolling } from "../hooks/useApiPolling";
import type { NarrativeOverview, NarrativeData, NarrativeTokenData } from "../types/narrative";

function formatVolume(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
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
    <button
      onClick={onClick}
      className="bg-terminal-card border border-terminal-border rounded-lg p-4 text-left hover:border-terminal-accent/40 transition-all w-full"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-terminal-text">{narrative.name}</span>
        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${lc} capitalize`}>
          {narrative.lifecycle}
        </span>
      </div>
      <div className="flex items-center gap-4 text-xs text-terminal-muted">
        <span>{narrative.token_count} tokens</span>
        <span>{formatVolume(narrative.total_volume)} vol</span>
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
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-terminal-accent/10 text-terminal-accent border border-terminal-accent/20">
              fork
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[11px] text-terminal-muted mt-0.5">
          {token.narrative && <span className="text-terminal-accent">{token.narrative}</span>}
          <span>{formatAge(token.created_at)}</span>
        </div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className={`text-sm font-bold tabular-nums ${
          (token.price_change_pct ?? 0) > 0 ? "text-terminal-green" : "text-terminal-red"
        }`}>
          {formatPct(token.price_change_pct)}
        </div>
        <div className="text-[11px] text-terminal-muted tabular-nums">
          {token.mcap ? formatVolume(token.mcap) : "--"}
        </div>
      </div>
      <a
        href={`https://dexscreener.com/solana/${token.address}`}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="text-[10px] text-terminal-accent/60 hover:text-terminal-accent flex-shrink-0"
      >
        DS
      </a>
    </div>
  );
}

export default function NarrativeDashboard() {
  const navigate = useNavigate();
  const { data, loading, error } = useApiPolling<NarrativeOverview>(
    "/narrative/overview",
    60000,
  );

  return (
    <PageLayout title="Narrative Tracker">
      <p className="text-sm text-terminal-muted mb-6">
        On-chain trending narratives and top runners — what to launch next
      </p>

      {loading && !data && (
        <div className="text-terminal-muted text-center py-16">Scanning trends...</div>
      )}
      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">
              Trending Narratives
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {data.narratives.map((n) => (
                <NarrativeCard
                  key={n.name}
                  narrative={n}
                  onClick={() => navigate(`/narrative/${encodeURIComponent(n.name)}`)}
                />
              ))}
            </div>
            {data.narratives.length === 0 && (
              <div className="text-terminal-muted text-center py-8 text-sm">
                No narratives detected yet — data populates every 20 minutes
              </div>
            )}
          </div>

          <div>
            <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">
              Top Runners (24h)
            </div>
            <div className="bg-terminal-card border border-terminal-border rounded-lg p-4">
              {data.top_runners.map((t) => (
                <RunnerRow key={t.address} token={t} />
              ))}
              {data.top_runners.length === 0 && (
                <div className="text-terminal-muted text-center py-6 text-sm">No runners yet</div>
              )}
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  );
}
