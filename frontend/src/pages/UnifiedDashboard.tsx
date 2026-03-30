import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import CandlestickChart, { type CandlestickChartHandle } from "../components/charts/CandlestickChart";
import { useApiPolling } from "../hooks/useApiPolling";
import { fetchChart } from "../api/pulse";
import type { ChartData } from "../types/pulse";
import type { LaunchOverviewData, LaunchPerformanceTiers } from "../types/launch";
import type { NarrativeOverview, NarrativeData, NarrativeTokenData } from "../types/narrative";

// ── Helpers ──

function fmt(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function fmtN(v: number): string {
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toLocaleString();
}

function fmtPct(v: number | null): string {
  if (v == null) return "--";
  return `${v > 0 ? "+" : ""}${v.toFixed(0)}%`;
}

function fmtTime(m: number | null): string {
  if (m == null) return "--";
  if (m < 60) return `${Math.round(m)}m`;
  const h = Math.floor(m / 60);
  if (h >= 24) { const d = Math.floor(h / 24); return d > 0 && h % 24 > 0 ? `${d}d ${h % 24}h` : `${d}d`; }
  return `${h}h ${Math.round(m % 60)}m`;
}

function fmtAge(c: string | null): string {
  if (!c) return "--";
  const h = Math.floor((Date.now() - new Date(c).getTime()) / 3600000);
  if (h >= 24) return `${Math.floor(h / 24)}d`;
  if (h > 0) return `${h}h`;
  return `${Math.floor((Date.now() - new Date(c).getTime()) / 60000)}m`;
}

function truncAddr(a: string): string {
  return a.length <= 10 ? a : `${a.slice(0, 4)}...${a.slice(-4)}`;
}

// ── Micro Components ──

function LivePulse() {
  return (
    <span className="relative flex h-1.5 w-1.5">
      <span className="animate-ping absolute h-full w-full rounded-full bg-terminal-green opacity-75" />
      <span className="relative rounded-full h-1.5 w-1.5 bg-terminal-green" />
    </span>
  );
}

function Tip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block ml-1">
      <button onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}
        className="text-terminal-muted/20 hover:text-terminal-muted/50 transition-colors text-[9px] w-3 h-3 rounded-full border border-terminal-muted/20 inline-flex items-center justify-center">?</button>
      <AnimatePresence>
        {show && (
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="absolute z-50 bottom-5 left-1/2 -translate-x-1/2 w-52 px-3 py-2 rounded-lg bg-[#1a1c2a] border border-white/10 text-[10px] text-terminal-muted leading-relaxed shadow-2xl">
            {text}
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  );
}

function SH({ t, info }: { t: string; info: string }) {
  return (
    <div className="flex items-center gap-1 mb-2">
      <span className="text-[9px] text-terminal-muted/40 uppercase tracking-[0.15em] font-medium">{t}</span>
      <Tip text={info} />
    </div>
  );
}

// ── Health Gauge ──

function HealthGauge({ score }: { score: number }) {
  const r = 44, circ = Math.PI * r, off = circ * (1 - score / 100);
  const color = score >= 70 ? "#00e676" : score <= 30 ? "#ff1744" : "#f0b90b";
  const label = score >= 70 ? "Launch Window" : score <= 30 ? "Danger Zone" : "Neutral";
  return (
    <div className="flex flex-col items-center">
      <svg width="100" height="58" viewBox="0 0 100 58">
        <path d="M 6 54 A 44 44 0 0 1 94 54" fill="none" stroke="#1e1e2e" strokeWidth={5} strokeLinecap="round" />
        <motion.path d="M 6 54 A 44 44 0 0 1 94 54" fill="none" stroke={color} strokeWidth={5} strokeLinecap="round"
          strokeDasharray={circ} initial={{ strokeDashoffset: circ }} animate={{ strokeDashoffset: off }}
          transition={{ duration: 1, ease: "easeOut" }} style={{ filter: `drop-shadow(0 0 6px ${color}40)` }} />
      </svg>
      <div className="text-center -mt-7">
        <div className="text-2xl font-bold" style={{ color }}>{score.toFixed(0)}</div>
        <div className="text-[8px] text-terminal-muted/60 uppercase tracking-wider">{label}</div>
      </div>
    </div>
  );
}

// ── Compact Launch Performance (inline) ──

function PerfTiers({ tiers }: { tiers: LaunchPerformanceTiers }) {
  const rows = [
    { k: "best24h" as const, label: "Best (24h)", color: "text-terminal-accent" },
    { k: "top10" as const, label: "Top 10%", color: "text-blue-400" },
    { k: "bonded" as const, label: "Bonded", color: "text-terminal-text" },
  ];
  const ttp = tiers.time_to_peak;
  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.k} className="flex items-center gap-2">
          <span className={`text-[11px] w-16 flex-shrink-0 ${r.color}`}>{r.label}</span>
          <div className="flex-1 h-1 rounded-full bg-white/[0.04] overflow-hidden">
            <div className={`h-full rounded-full bg-current ${r.color}`}
              style={{ width: `${Math.max(2, (Math.log10(tiers[r.k] + 1) / Math.log10(tiers.best24h + 1)) * 100)}%` }} />
          </div>
          <span className={`text-[11px] font-bold tabular-nums w-14 text-right ${r.color}`}>{fmt(tiers[r.k])}</span>
          <span className="text-[10px] tabular-nums w-12 text-right text-terminal-muted/50">{fmtTime(ttp?.[r.k] ?? null)}</span>
        </div>
      ))}
      {tiers.all_median != null && (
        <div className="flex items-center gap-2 pt-1 border-t border-white/[0.04]">
          <span className="text-[11px] w-16 flex-shrink-0 text-terminal-red/70">All</span>
          <div className="flex-1 h-1 rounded-full bg-white/[0.04] overflow-hidden">
            <div className="h-full rounded-full bg-terminal-red/60"
              style={{ width: `${Math.max(2, (Math.log10(tiers.all_median + 1) / Math.log10(tiers.best24h + 1)) * 100)}%` }} />
          </div>
          <span className="text-[11px] font-bold tabular-nums w-14 text-right text-terminal-red/70">{fmt(tiers.all_median)}</span>
          <span className="w-12" />
        </div>
      )}
      {tiers.best_address && (
        <div className="text-[9px] text-terminal-muted/40 pt-1">
          <span className="font-mono">{truncAddr(tiers.best_address)}</span>
          {" "}
          <a href={`https://dexscreener.com/solana/${tiers.best_address}`} target="_blank" rel="noopener noreferrer"
            className="text-terminal-accent/50 hover:text-terminal-accent underline">DexScreener</a>
        </div>
      )}
    </div>
  );
}

// ── Compact Launchpad Activity (inline) ──

function LaunchpadBars({ breakdown, total, graduated, rate }: {
  breakdown: Record<string, number>; total: number; graduated: number; rate: number | null;
}) {
  const LP: Record<string, string> = { pumpdotfun: "pump.fun", letsbonk: "LetsBonk", bags: "Bags", moonshot: "Moonshot", jupstudio: "Jup Studio", launchlab: "LaunchLab" };
  const sorted = Object.entries(breakdown).filter(([k, v]) => v > 0 && k !== "moon.it").sort((a, b) => b[1] - a[1]);
  const max = sorted[0]?.[1] || 1;
  const colors = ["bg-terminal-accent", "bg-terminal-green", "bg-blue-400", "bg-purple-400", "bg-pink-400", "bg-cyan-400"];

  return (
    <div>
      <div className="flex items-baseline gap-4 mb-3">
        <div><span className="text-xl font-bold text-terminal-text">{fmtN(total)}</span><span className="text-[10px] text-terminal-muted ml-1">launches</span></div>
        {graduated > 0 && <div><span className="text-lg font-bold text-terminal-green">{fmtN(graduated)}</span><span className="text-[10px] text-terminal-muted ml-1">grads</span></div>}
        {rate != null && rate > 0 && <div><span className="text-lg font-bold text-terminal-accent">{rate.toFixed(1)}%</span></div>}
      </div>
      <div className="space-y-1">
        {sorted.slice(0, 5).map(([k, v], i) => (
          <div key={k} className="flex items-center gap-2">
            <span className="text-[10px] text-terminal-text w-16 truncate">{LP[k] || k}</span>
            <div className="flex-1 h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
              <div className={`h-full rounded-full ${colors[i % colors.length]}`} style={{ width: `${Math.max(2, (v / max) * 100)}%` }} />
            </div>
            <span className="text-[10px] tabular-nums text-terminal-muted w-12 text-right">{v.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Narrative Card ──

const LC: Record<string, string> = {
  emerging: "text-blue-400 border-blue-400/20", trending: "text-terminal-green border-terminal-green/20",
  saturated: "text-terminal-accent border-terminal-accent/20", fading: "text-terminal-red border-terminal-red/20",
};

function NCard({ n, i, onClick }: { n: NarrativeData; i: number; onClick: () => void }) {
  return (
    <motion.button onClick={onClick} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay: i * 0.04, duration: 0.25 }}
      className="bg-white/[0.02] border border-white/[0.05] rounded-lg p-2.5 text-left hover:border-terminal-accent/20 hover:bg-white/[0.04] transition-all w-full">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-bold text-terminal-text">{n.name}</span>
        <span className={`text-[8px] px-1.5 py-0.5 rounded-full border ${LC[n.lifecycle] || LC.fading} capitalize`}>{n.lifecycle}</span>
      </div>
      <div className="flex items-center gap-2 text-[10px] text-terminal-muted">
        <span>{n.token_count} tok</span>
        <span>{fmt(n.total_volume)}</span>
        <span className={n.avg_gain_pct > 0 ? "text-terminal-green" : "text-terminal-red"}>{fmtPct(n.avg_gain_pct)}</span>
      </div>
    </motion.button>
  );
}

// ── Runner Row ──

function RRow({ t, i }: { t: NarrativeTokenData; i: number }) {
  return (
    <motion.div initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04, duration: 0.2 }}
      className="flex items-center gap-2 py-1 border-b border-white/[0.03] last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1">
          <span className="text-[11px] font-medium text-terminal-text truncate">{t.name}</span>
          {!t.is_original && <span className="text-[7px] px-1 rounded bg-terminal-accent/10 text-terminal-accent">fork</span>}
        </div>
        <div className="flex items-center gap-1 text-[9px] text-terminal-muted">
          {t.narrative && <span className="text-terminal-accent">{t.narrative}</span>}
          <span>{fmtAge(t.created_at)}</span>
        </div>
      </div>
      <span className={`text-[11px] font-bold tabular-nums ${(t.price_change_pct ?? 0) > 0 ? "text-terminal-green" : "text-terminal-red"}`}>
        {fmtPct(t.price_change_pct)}
      </span>
      <span className="text-[9px] tabular-nums text-terminal-muted w-10 text-right">{t.mcap ? fmt(t.mcap) : "--"}</span>
      <a href={`https://dexscreener.com/solana/${t.address}`} target="_blank" rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()} className="text-[8px] text-terminal-accent/30 hover:text-terminal-accent">DS</a>
    </motion.div>
  );
}

// ── Glass Card wrapper ──

function GCard({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.35 }}
      className={`bg-white/[0.02] backdrop-blur-sm border border-white/[0.06] rounded-xl p-4 ${className}`}>
      {children}
    </motion.div>
  );
}

// ── Main Dashboard ──

export default function UnifiedDashboard() {
  const navigate = useNavigate();
  const chartRef = useRef<CandlestickChartHandle>(null);
  const rangeSet = useRef(false);

  const [chartData, setChartData] = useState<ChartData | null>(null);
  const { data: launch } = useApiPolling<LaunchOverviewData>("/launch/overview?range=30d", 60000);
  const { data: narr } = useApiPolling<NarrativeOverview>("/narrative/overview", 60000);

  useEffect(() => {
    const exc = ["dex_volume", "stablecoin_supply", "vol_regime", "new_wallets", "priority_fees"];
    fetchChart("all", exc).then(setChartData).catch(() => {});
    const iv = setInterval(async () => {
      try {
        const d = await fetchChart("all", exc);
        setChartData((p) => {
          if (!p || d.candles.length !== p.candles.length) return d;
          if (d.candles[d.candles.length - 1]?.close !== p.candles[p.candles.length - 1]?.close) return d;
          return p;
        });
      } catch {}
    }, 60000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (!chartData || rangeSet.current) return;
    const t = setTimeout(() => { chartRef.current?.getChart()?.timeScale().fitContent(); rangeSet.current = true; }, 500);
    return () => clearTimeout(t);
  }, [chartData]);

  const score = chartData?.scores?.length ? chartData.scores[chartData.scores.length - 1].score : null;
  const perf = launch?.metrics.find(m => m.name === "Launch Performance");
  const tiers = perf?.tiers;
  const act = launch?.metrics.find(m => m.name === "Launchpad Activity");
  const launches = act?.current ?? 0;
  const rate = (act as Record<string, unknown> | undefined)?.migration_rate as number | undefined;
  const grads = (act as Record<string, unknown> | undefined)?.total_graduated as number | undefined;
  const breakdown = act?.breakdown as Record<string, number> | undefined;
  const surv = launch?.metrics.find(m => m.name === "Survival Rate (24h)");
  const vol = launch?.metrics.find(m => m.name === "Volume");

  return (
    <div className="max-w-[1400px] mx-auto">
      {/* Background mesh */}
      <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden">
        <div className="absolute -top-32 -left-32 w-[500px] h-[500px] bg-purple-900/[0.06] rounded-full blur-[100px]" />
        <div className="absolute -bottom-32 -right-32 w-[400px] h-[400px] bg-cyan-900/[0.04] rounded-full blur-[100px]" />
      </div>

      {/* ── Header Bar ── */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-terminal-accent font-bold text-base tracking-[0.2em]">CANDLE</span>
          <LivePulse />
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          <span className="text-terminal-muted/40">Launches <span className="text-terminal-text font-bold">{fmtN(launches)}</span></span>
          {rate != null && <span className="text-terminal-muted/40">Grad <span className="text-terminal-text font-bold">{rate.toFixed(1)}%</span></span>}
          {surv?.current != null && <span className="text-terminal-muted/40">Survival <span className="text-terminal-text font-bold">{surv.current.toFixed(0)}%</span></span>}
          {vol?.current != null && <span className="text-terminal-muted/40">Vol <span className="text-terminal-text font-bold">{fmt(vol.current)}</span></span>}
        </div>
      </motion.div>

      {/* ── Row 1: Gauge | Chart ── */}
      <div className="grid grid-cols-[120px_1fr] gap-3 mb-3">
        <GCard className="flex flex-col items-center justify-center !p-3" delay={0.05}>
          {score !== null ? <HealthGauge score={score} /> : <div className="text-terminal-muted text-[10px]">...</div>}
          <Tip text="Health score from TVL, Fear & Greed, Chain Fees. Higher = better launch conditions." />
        </GCard>
        <GCard className="!p-0 overflow-hidden" delay={0.1}>
          {chartData && chartData.candles.length > 0 ? (
            <CandlestickChart ref={chartRef} candles={chartData.candles} scores={chartData.scores} height={160} />
          ) : (
            <div className="h-[160px] flex items-center justify-center text-terminal-muted text-[10px]">Loading...</div>
          )}
        </GCard>
      </div>

      {/* ── Row 2: Performance | Activity ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3">
        <GCard delay={0.15}>
          <SH t="Launch Performance" info="Peak market cap tiers for graduated tokens in the last 24h. Shows what different launches achieve." />
          {tiers ? <PerfTiers tiers={tiers} /> : <div className="text-terminal-muted text-[10px]">Loading...</div>}
        </GCard>
        <GCard delay={0.2}>
          <SH t="Launchpad Activity" info="Token launches across all platforms with graduation rate. Data from Dune on-chain analytics." />
          {breakdown ? (
            <LaunchpadBars breakdown={breakdown} total={launches} graduated={grads ?? 0} rate={rate ?? null} />
          ) : (
            <div className="text-terminal-muted text-[10px]">Loading...</div>
          )}
        </GCard>
      </div>

      {/* ── Row 3: Narratives | Runners ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-3">
        <div>
          <SH t="Trending Narratives" info="AI-classified token themes from DexScreener. Shows what categories are hot. Click to see tokens." />
          <div className="bg-terminal-red/[0.03] border border-terminal-red/10 rounded px-2 py-1 mb-2">
            <p className="text-[9px] text-terminal-red/50">Includes unverified tokens for narrative identification. Not investment advice.</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-2">
            {narr?.narratives.map((n, i) => (
              <NCard key={n.name} n={n} i={i} onClick={() => navigate(`/narrative/${encodeURIComponent(n.name)}`)} />
            ))}
          </div>
          {(!narr || narr.narratives.length === 0) && (
            <div className="text-terminal-muted text-center py-6 text-[11px]">Scanning narratives...</div>
          )}
        </div>
        <div>
          <SH t="Top Runners" info="Tokens with highest % gain in 24h. DS = DexScreener link." />
          <GCard className="!p-3" delay={0.25}>
            {narr?.top_runners.map((t, i) => <RRow key={t.address} t={t} i={i} />)}
            {(!narr || narr.top_runners.length === 0) && (
              <div className="text-terminal-muted text-center py-4 text-[10px]">No runners yet</div>
            )}
          </GCard>
        </div>
      </div>
    </div>
  );
}
