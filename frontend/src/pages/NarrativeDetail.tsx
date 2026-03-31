import { useParams, useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import { useApiPolling } from "../hooks/useApiPolling";
import type { NarrativeDetail as NarrativeDetailData } from "../types/narrative";

const $=(v:number)=>v>=1e9?`$${(v/1e9).toFixed(1)}B`:v>=1e6?`$${(v/1e6).toFixed(1)}M`:v>=1e3?`$${(v/1e3).toFixed(0)}K`:`$${v.toFixed(0)}`;
const P=(v:number|null)=>v==null?"--":`${v>0?"+":""}${v.toFixed(0)}%`;
const A=(c:string|null)=>{if(!c)return"--";const h=Math.floor((Date.now()-new Date(c).getTime())/36e5);return h>=24?`${Math.floor(h/24)}d`:h>0?`${h}h`:`${Math.floor((Date.now()-new Date(c).getTime())/6e4)}m`;};

const LC_COL:Record<string,string>={emerging:"text-blue-400",trending:"text-emerald-400",saturated:"text-amber-400",fading:"text-red-400"};
const DS_ICON="https://dd.dexscreener.com/ds-data/dapps/dexscreener.png";

export default function NarrativeDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const { data, loading, error } = useApiPolling<NarrativeDetailData>(
    `/narrative/${encodeURIComponent(name || "")}`, 60000,
  );

  return (
    <PageLayout title={name || "Narrative"}>
      <button onClick={() => navigate("/")}
        className="text-sm text-white/30 hover:text-white/60 transition-colors mb-6">
        ← Back to dashboard
      </button>

      {loading && !data && <div className="text-white/20 text-center py-16 animate-pulse">Loading...</div>}
      {error && <div className="text-red-400 text-center py-4 text-sm">{error}</div>}

      {data && (
        <>
          {/* Stats bar */}
          <div className="bg-white/[0.02] backdrop-blur-sm border border-white/[0.06] rounded-2xl p-5 mb-5">
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-6">
              {[
                { label: "Lifecycle", value: data.lifecycle, color: LC_COL[data.lifecycle] || "text-white/70", capitalize: true },
                { label: "Tokens", value: data.token_count, color: "text-white" },
                { label: "Total Mcap", value: $(data.total_mcap || 0), color: "text-white" },
                { label: "Avg Mcap", value: $(data.avg_mcap || 0), color: "text-white" },
                { label: "Volume", value: $(data.total_volume), color: "text-white" },
                { label: "Avg Gain", value: P(data.avg_gain_pct), color: data.avg_gain_pct > 0 ? "text-emerald-400" : "text-red-400" },
              ].map((s) => (
                <div key={s.label}>
                  <div className="text-[10px] text-white/30 uppercase tracking-wider mb-1">{s.label}</div>
                  <div className={`text-lg font-bold ${s.color} ${s.capitalize ? "capitalize" : ""}`}>{s.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Token table */}
          <div className="text-xs text-white/40 uppercase tracking-wider mb-3 font-bold">Tokens in this narrative</div>
          <div className="bg-white/[0.02] backdrop-blur-sm border border-white/[0.06] rounded-2xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="text-[10px] text-white/20 uppercase tracking-wider border-b border-white/[0.06]">
                  <th className="text-left p-3 font-medium">Token</th>
                  <th className="text-right p-3 font-medium">Mcap</th>
                  <th className="text-right p-3 font-medium">ATH</th>
                  <th className="text-right p-3 font-medium">Change</th>
                  <th className="text-right p-3 font-medium">Volume</th>
                  <th className="text-right p-3 font-medium">Age</th>
                  <th className="text-right p-3 font-medium">Type</th>
                  <th className="text-right p-3 font-medium w-8"></th>
                </tr>
              </thead>
              <tbody>
                {data.tokens.map((t) => (
                  <tr key={t.address} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                    <td className="p-3">
                      <a href={`https://dexscreener.com/solana/${t.address}`} target="_blank" rel="noopener noreferrer"
                        className="text-sm font-semibold text-white/80 hover:text-amber-400 transition-colors">{t.name}</a>
                      <div className="text-[10px] text-white/25">{t.symbol}</div>
                    </td>
                    <td className="p-3 text-right text-sm tabular-nums text-white/70">{t.mcap ? $(t.mcap) : "--"}</td>
                    <td className="p-3 text-right text-sm tabular-nums text-amber-400/70">
                      {(t as Record<string, unknown>).mcap_ath ? $((t as Record<string, unknown>).mcap_ath as number) : "--"}
                    </td>
                    <td className={`p-3 text-right text-sm font-bold tabular-nums ${(t.price_change_pct ?? 0) > 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {P(t.price_change_pct)}
                    </td>
                    <td className="p-3 text-right text-sm tabular-nums text-white/30">{t.volume_24h ? $(t.volume_24h) : "--"}</td>
                    <td className="p-3 text-right text-sm tabular-nums text-white/30">{A(t.created_at)}</td>
                    <td className="p-3 text-right text-xs">
                      {t.is_original
                        ? <span className="text-emerald-400/60 bg-emerald-400/10 px-1.5 py-0.5 rounded text-[9px]">original</span>
                        : <span className="text-amber-400/60 bg-amber-400/10 px-1.5 py-0.5 rounded text-[9px]">fork</span>}
                    </td>
                    <td className="p-3 text-right">
                      <a href={`https://dexscreener.com/solana/${t.address}`} target="_blank" rel="noopener noreferrer">
                        <img src={DS_ICON} alt="" className="w-4 h-4 rounded inline-block opacity-30 hover:opacity-100 transition-opacity"
                          onError={e=>{(e.target as HTMLImageElement).style.display='none'}}/>
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
