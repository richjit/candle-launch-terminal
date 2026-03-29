import { useParams, useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import { useApiPolling } from "../hooks/useApiPolling";
import type { NarrativeDetail as NarrativeDetailData } from "../types/narrative";

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
  if (h >= 24) return `${Math.floor(h / 24)}d`;
  if (h > 0) return `${h}h`;
  return `${Math.floor(diff / 60000)}m`;
}

export default function NarrativeDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const { data, loading, error } = useApiPolling<NarrativeDetailData>(
    `/narrative/${encodeURIComponent(name || "")}`,
    60000,
  );

  return (
    <PageLayout title={name || "Narrative"}>
      <button
        onClick={() => navigate("/narrative")}
        className="text-sm text-terminal-muted hover:text-terminal-text transition-colors mb-6"
      >
        ← Back to narratives
      </button>

      {loading && !data && <div className="text-terminal-muted text-center py-16">Loading...</div>}
      {error && <div className="text-terminal-red text-center py-4 text-sm">{error}</div>}

      {data && (
        <>
          <div className="bg-terminal-card border border-terminal-border rounded-lg p-5 mb-6">
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-6">
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Lifecycle</div>
                <div className="text-lg font-bold text-terminal-text capitalize">{data.lifecycle}</div>
              </div>
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Tokens</div>
                <div className="text-lg font-bold text-terminal-text">{data.token_count}</div>
              </div>
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Total Mcap</div>
                <div className="text-lg font-bold text-terminal-text">{formatVolume(data.total_mcap || 0)}</div>
              </div>
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Avg Mcap</div>
                <div className="text-lg font-bold text-terminal-text">{formatVolume(data.avg_mcap || 0)}</div>
              </div>
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Volume</div>
                <div className="text-lg font-bold text-terminal-text">{formatVolume(data.total_volume)}</div>
              </div>
              <div>
                <div className="text-xs text-terminal-muted uppercase mb-1">Avg Gain</div>
                <div className={`text-lg font-bold ${data.avg_gain_pct > 0 ? "text-terminal-green" : "text-terminal-red"}`}>
                  {formatPct(data.avg_gain_pct)}
                </div>
              </div>
            </div>
          </div>

          <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">
            Tokens in this narrative
          </div>
          <div className="bg-terminal-card border border-terminal-border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="text-[11px] text-terminal-muted/50 uppercase tracking-wider border-b border-terminal-border/30">
                  <th className="text-left p-3 font-medium">Token</th>
                  <th className="text-right p-3 font-medium">Mcap</th>
                  <th className="text-right p-3 font-medium">ATH</th>
                  <th className="text-right p-3 font-medium">Change</th>
                  <th className="text-right p-3 font-medium">Volume</th>
                  <th className="text-right p-3 font-medium">Age</th>
                  <th className="text-right p-3 font-medium">Type</th>
                  <th className="text-right p-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {data.tokens.map((t) => (
                  <tr key={t.address} className="border-b border-terminal-border/10 hover:bg-terminal-border/5">
                    <td className="p-3">
                      <div className="text-sm font-medium text-terminal-text">{t.name}</div>
                      <div className="text-[11px] text-terminal-muted">{t.symbol}</div>
                    </td>
                    <td className="p-3 text-right text-sm tabular-nums text-terminal-text">
                      {t.mcap ? formatVolume(t.mcap) : "--"}
                    </td>
                    <td className="p-3 text-right text-sm tabular-nums text-terminal-accent">
                      {(t as Record<string, unknown>).mcap_ath ? formatVolume((t as Record<string, unknown>).mcap_ath as number) : "--"}
                    </td>
                    <td className={`p-3 text-right text-sm font-bold tabular-nums ${
                      (t.price_change_pct ?? 0) > 0 ? "text-terminal-green" : "text-terminal-red"
                    }`}>
                      {formatPct(t.price_change_pct)}
                    </td>
                    <td className="p-3 text-right text-sm tabular-nums text-terminal-muted">
                      {t.volume_24h ? formatVolume(t.volume_24h) : "--"}
                    </td>
                    <td className="p-3 text-right text-sm tabular-nums text-terminal-muted">
                      {formatAge(t.created_at)}
                    </td>
                    <td className="p-3 text-right text-xs">
                      {t.is_original ? (
                        <span className="text-terminal-green">original</span>
                      ) : (
                        <span className="text-terminal-accent">fork</span>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      <a
                        href={`https://dexscreener.com/solana/${t.address}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-terminal-accent/60 hover:text-terminal-accent underline"
                      >
                        DexScreener
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </PageLayout>
  );
}
