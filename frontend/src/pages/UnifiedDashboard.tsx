import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import CandlestickChart, { type CandlestickChartHandle } from "../components/charts/CandlestickChart";
import { useApiPolling } from "../hooks/useApiPolling";
import { fetchChart } from "../api/pulse";
import type { ChartData } from "../types/pulse";
import type { LaunchOverviewData, LaunchPerformanceTiers } from "../types/launch";
import type { NarrativeOverview, NarrativeData, NarrativeTokenData } from "../types/narrative";

// ── Formatters ──
const $ = (v: number) => v >= 1e9 ? `$${(v/1e9).toFixed(1)}B` : v >= 1e6 ? `$${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `$${(v/1e3).toFixed(1)}K` : `$${v.toFixed(0)}`;
const n = (v: number) => v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(1)}K` : v.toLocaleString();
const pct = (v: number|null) => v == null ? "--" : `${v > 0 ? "+" : ""}${v.toFixed(0)}%`;
const tm = (m: number|null) => { if (m == null) return "--"; if (m < 60) return `${Math.round(m)}m`; const h = Math.floor(m/60); if (h >= 24) { const d = Math.floor(h/24); const rh = h%24; return rh ? `${d}d ${rh}h` : `${d}d`; } return `${h}h ${Math.round(m%60)}m`; };
const age = (c: string|null) => { if (!c) return "--"; const h = Math.floor((Date.now()-new Date(c).getTime())/36e5); return h >= 24 ? `${Math.floor(h/24)}d` : h > 0 ? `${h}h` : `${Math.floor((Date.now()-new Date(c).getTime())/6e4)}m`; };

// ── Animated Number ──
function Counter({ value, duration = 700 }: { value: number; duration?: number }) {
  const [d, setD] = useState(0);
  const prev = useRef(0);
  useEffect(() => {
    const s = prev.current, e = value, t0 = Date.now();
    const tick = () => { const p = Math.min((Date.now()-t0)/duration, 1); setD(Math.round(s+(e-s)*(1-Math.pow(1-p,3)))); if (p < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick); prev.current = value;
  }, [value, duration]);
  return <>{d.toLocaleString()}</>;
}

// ── Health Gauge ──
function Gauge({ score }: { score: number }) {
  const r = 40, c = Math.PI*r, off = c*(1-score/100);
  const col = score >= 70 ? "#00e676" : score <= 30 ? "#ff1744" : "#f0b90b";
  const lab = score >= 70 ? "LAUNCH WINDOW" : score <= 30 ? "DANGER ZONE" : "NEUTRAL";
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <svg width="90" height="52" viewBox="0 0 90 52">
        <path d="M 5 48 A 40 40 0 0 1 85 48" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth={4} strokeLinecap="round"/>
        <motion.path d="M 5 48 A 40 40 0 0 1 85 48" fill="none" stroke={col} strokeWidth={4} strokeLinecap="round"
          strokeDasharray={c} initial={{strokeDashoffset:c}} animate={{strokeDashoffset:off}}
          transition={{duration:1.2,ease:"easeOut"}} style={{filter:`drop-shadow(0 0 8px ${col}50)`}}/>
      </svg>
      <div className="-mt-6 text-center">
        <div className="text-2xl font-black tracking-tight" style={{color:col}}>{score.toFixed(0)}</div>
        <div className="text-[7px] tracking-[0.2em] mt-0.5" style={{color:`${col}99`}}>{lab}</div>
      </div>
    </div>
  );
}

// ── Live Dot ──
function Live() {
  return <span className="relative flex h-1.5 w-1.5 ml-1.5">
    <span className="animate-ping absolute h-full w-full rounded-full bg-emerald-400 opacity-60"/>
    <span className="relative rounded-full h-1.5 w-1.5 bg-emerald-400"/>
  </span>;
}

// ── Tooltip ──
function Tip({ text }: { text: string }) {
  const [s, set] = useState(false);
  return <span className="relative ml-1 inline-block">
    <button onMouseEnter={()=>set(true)} onMouseLeave={()=>set(false)}
      className="w-3.5 h-3.5 rounded-full border border-white/10 text-white/15 hover:text-white/40 hover:border-white/20 text-[8px] inline-flex items-center justify-center transition-colors">?</button>
    <AnimatePresence>{s && <motion.div initial={{opacity:0,y:4}} animate={{opacity:1,y:0}} exit={{opacity:0}}
      className="absolute z-50 bottom-6 left-1/2 -translate-x-1/2 w-56 px-3 py-2 rounded-lg bg-[#1a1c2e] border border-white/10 text-[10px] text-white/60 leading-relaxed shadow-2xl pointer-events-none">{text}</motion.div>}</AnimatePresence>
  </span>;
}

// ── Section label ──
function Label({ children, tip }: { children: string; tip: string }) {
  return <div className="flex items-center mb-2"><span className="text-[9px] text-white/25 uppercase tracking-[0.15em] font-semibold">{children}</span><Tip text={tip}/></div>;
}

// ── Stat box ──
function Stat({ label, value, sub, color = "text-white" }: { label: string; value: React.ReactNode; sub?: string; color?: string }) {
  return <div className="text-center">
    <div className={`text-lg font-bold ${color}`}>{value}</div>
    <div className="text-[8px] text-white/30 uppercase tracking-wider">{label}</div>
    {sub && <div className="text-[9px] text-white/20">{sub}</div>}
  </div>;
}

// ── Narrative Card ──
const LC_BG: Record<string,string> = {
  emerging:"from-blue-500/10 to-transparent border-blue-500/15", trending:"from-emerald-500/10 to-transparent border-emerald-500/15",
  saturated:"from-amber-500/8 to-transparent border-amber-500/12", fading:"from-red-500/8 to-transparent border-red-500/12"
};
const LC_TEXT: Record<string,string> = { emerging:"text-blue-400", trending:"text-emerald-400", saturated:"text-amber-400", fading:"text-red-400" };

function NarrCard({ n: nr, i, onClick }: { n: NarrativeData; i: number; onClick: () => void }) {
  const bg = LC_BG[nr.lifecycle] || LC_BG.fading;
  const tc = LC_TEXT[nr.lifecycle] || LC_TEXT.fading;
  return (
    <motion.button onClick={onClick} initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{delay:i*0.04,duration:0.25}}
      className={`bg-gradient-to-br ${bg} border rounded-lg p-3 text-left hover:scale-[1.02] transition-all w-full group`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[13px] font-bold text-white/90 group-hover:text-white">{nr.name}</span>
        <span className={`text-[8px] font-semibold uppercase tracking-wider ${tc}`}>{nr.lifecycle}</span>
      </div>
      <div className="flex items-center gap-3 text-[10px] text-white/35">
        <span className="text-white/50 font-medium">{nr.token_count} tokens</span>
        <span>{$(nr.total_volume)} vol</span>
        <span className={nr.avg_gain_pct > 0 ? "text-emerald-400 font-bold" : "text-red-400 font-bold"}>{pct(nr.avg_gain_pct)}</span>
      </div>
    </motion.button>
  );
}

// ── Runner Row ──
function Runner({ t, i }: { t: NarrativeTokenData; i: number }) {
  const up = (t.price_change_pct ?? 0) > 0;
  return (
    <motion.div initial={{opacity:0,x:8}} animate={{opacity:1,x:0}} transition={{delay:i*0.03,duration:0.2}}
      className="flex items-center gap-2 py-1.5 border-b border-white/[0.03] last:border-0 group">
      <div className="flex-1 min-w-0">
        <div className="text-[11px] font-semibold text-white/80 group-hover:text-white truncate">{t.name}</div>
        <div className="text-[9px] text-white/25">
          {t.narrative && <span className="text-amber-400/60">{t.narrative}</span>}
          {t.narrative && <span className="mx-1">·</span>}
          {age(t.created_at)}
        </div>
      </div>
      <div className={`text-[11px] font-bold tabular-nums px-1.5 py-0.5 rounded ${up ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"}`}>
        {pct(t.price_change_pct)}
      </div>
      <span className="text-[9px] tabular-nums text-white/25 w-12 text-right">{t.mcap ? $(t.mcap) : "--"}</span>
      <a href={`https://dexscreener.com/solana/${t.address}`} target="_blank" rel="noopener noreferrer"
        onClick={e=>e.stopPropagation()} className="text-[8px] text-amber-400/20 hover:text-amber-400 transition-colors">DS</a>
    </motion.div>
  );
}

// ── Glass Panel ──
function Panel({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  return <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{delay,duration:0.3}}
    className={`bg-white/[0.02] backdrop-blur-sm border border-white/[0.05] rounded-xl ${className}`}>{children}</motion.div>;
}

// ── Performance bars ──
function PerfRow({ label, value, max, time, color }: { label: string; value: number; max: number; time: number|null; color: string }) {
  const w = Math.max(3, (Math.log10(value+1)/Math.log10(max+1))*100);
  return <div className="flex items-center gap-2 py-1">
    <span className={`text-[10px] w-14 ${color} font-medium`}>{label}</span>
    <div className="flex-1 h-[3px] rounded-full bg-white/[0.04] overflow-hidden">
      <motion.div initial={{width:0}} animate={{width:`${w}%`}} transition={{duration:0.8,ease:"easeOut"}}
        className={`h-full rounded-full`} style={{background: color.includes("amber") ? "#f0b90b" : color.includes("blue") ? "#60a5fa" : color.includes("emerald") ? "#34d399" : color.includes("red") ? "#f87171" : "#e5e7eb"}}/>
    </div>
    <span className={`text-[11px] font-bold tabular-nums w-14 text-right ${color}`}>{$(value)}</span>
    <span className="text-[9px] tabular-nums text-white/20 w-10 text-right">{tm(time)}</span>
  </div>;
}

// ── Launchpad bar ──
const LP_NAMES: Record<string,string> = { pumpdotfun:"pump.fun", letsbonk:"LetsBonk", bags:"Bags", moonshot:"Moonshot", jupstudio:"Jup Studio", launchlab:"LaunchLab" };
const BAR_COLS = ["#f0b90b","#34d399","#60a5fa","#c084fc","#f472b6","#22d3ee"];

function LPBar({ name, value, max, color }: { name: string; value: number; max: number; color: string }) {
  return <div className="flex items-center gap-2 py-0.5">
    <span className="text-[10px] text-white/50 w-16 truncate">{LP_NAMES[name]||name}</span>
    <div className="flex-1 h-[3px] rounded-full bg-white/[0.04] overflow-hidden">
      <motion.div initial={{width:0}} animate={{width:`${Math.max(2,(value/max)*100)}%`}} transition={{duration:0.6,ease:"easeOut"}}
        className="h-full rounded-full" style={{background:color}}/>
    </div>
    <span className="text-[9px] tabular-nums text-white/30 w-12 text-right">{value.toLocaleString()}</span>
  </div>;
}

// ══════════════════════════════════════════════════════════════
// MAIN DASHBOARD
// ══════════════════════════════════════════════════════════════

export default function UnifiedDashboard() {
  const nav = useNavigate();
  const cRef = useRef<CandlestickChartHandle>(null);
  const rangeSet = useRef(false);

  const [chart, setChart] = useState<ChartData|null>(null);
  const { data: launch } = useApiPolling<LaunchOverviewData>("/launch/overview?range=30d", 60000);
  const { data: narr } = useApiPolling<NarrativeOverview>("/narrative/overview", 60000);

  // Chart fetch
  useEffect(() => {
    const x = ["dex_volume","stablecoin_supply","vol_regime","new_wallets","priority_fees"];
    fetchChart("all",x).then(setChart).catch(()=>{});
    const iv = setInterval(async()=>{try{const d=await fetchChart("all",x);setChart(p=>{if(!p||d.candles.length!==p.candles.length)return d;if(d.candles[d.candles.length-1]?.close!==p.candles[p.candles.length-1]?.close)return d;return p;});}catch{}},60000);
    return ()=>clearInterval(iv);
  }, []);

  useEffect(() => {
    if (!chart || rangeSet.current) return;
    const t = setTimeout(()=>{cRef.current?.getChart()?.timeScale().fitContent();rangeSet.current=true;},500);
    return ()=>clearTimeout(t);
  }, [chart]);

  // Extract data
  const score = chart?.scores?.length ? chart.scores[chart.scores.length-1].score : null;
  const perf = launch?.metrics.find(m=>m.name==="Launch Performance");
  const tiers = perf?.tiers;
  const act = launch?.metrics.find(m=>m.name==="Launchpad Activity");
  const launches = act?.current ?? 0;
  const gradRate = (act as any)?.migration_rate as number|undefined;
  const graduated = (act as any)?.total_graduated as number|undefined;
  const bd = (act?.breakdown || {}) as Record<string,number>;
  const surv = launch?.metrics.find(m=>m.name==="Survival Rate (24h)");
  const bs = launch?.metrics.find(m=>m.name==="Buy/Sell Ratio");
  const vol = launch?.metrics.find(m=>m.name==="Volume");

  const sorted = Object.entries(bd).filter(([k,v])=>v>0&&k!=="moon.it").sort((a,b)=>b[1]-a[1]);
  const maxLP = sorted[0]?.[1] || 1;

  return (
    <div className="w-full min-h-screen -m-6 p-4 lg:p-5 relative overflow-hidden">
      {/* Background */}
      <div className="fixed inset-0 pointer-events-none -z-10">
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] bg-purple-900/[0.05] rounded-full blur-[120px]"/>
        <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] bg-cyan-900/[0.04] rounded-full blur-[120px]"/>
        <div className="absolute inset-0" style={{backgroundImage:"radial-gradient(circle, rgba(255,255,255,0.015) 1px, transparent 1px)", backgroundSize:"32px 32px"}}/>
      </div>

      {/* ── Header ── */}
      <motion.div initial={{opacity:0}} animate={{opacity:1}} className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5">
          <span className="text-amber-400 font-black text-sm tracking-[0.25em]">CANDLE</span>
          <Live/>
        </div>
        <div className="flex items-center gap-5 text-[10px] text-white/30">
          <span>{n(launches)} <span className="text-white/15">launches</span></span>
          {gradRate!=null && <span>{gradRate.toFixed(1)}% <span className="text-white/15">graduation</span></span>}
          {surv?.current!=null && <span>{surv.current.toFixed(0)}% <span className="text-white/15">survival</span></span>}
          {bs?.current!=null && <span>{bs.current.toFixed(2)} <span className="text-white/15">buy/sell</span></span>}
          {vol?.current!=null && <span>{$(vol.current)} <span className="text-white/15">volume</span></span>}
        </div>
      </motion.div>

      {/* ── Row 1: Gauge | Chart | Quick Stats ── */}
      <div className="grid grid-cols-[110px_1fr_200px] gap-3 mb-3">
        <Panel className="p-3 flex items-center justify-center" delay={0.05}>
          {score !== null ? <Gauge score={score}/> : <div className="text-white/20 text-[9px]">Loading...</div>}
        </Panel>
        <Panel className="!p-0 overflow-hidden" delay={0.1}>
          {chart && chart.candles.length > 0 ? (
            <CandlestickChart ref={cRef} candles={chart.candles} scores={chart.scores} height={150}/>
          ) : <div className="h-[150px] flex items-center justify-center text-white/20 text-[10px]">Loading chart...</div>}
        </Panel>
        <Panel className="p-3 flex flex-col justify-center gap-3" delay={0.15}>
          <Stat label="Launches (24h)" value={<Counter value={launches}/>}/>
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Graduated" value={graduated != null ? <Counter value={graduated}/> : "--"} color="text-emerald-400"/>
            <Stat label="Graduation" value={gradRate != null ? `${gradRate.toFixed(1)}%` : "--"} color="text-amber-400"/>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Survival" value={surv?.current != null ? `${surv.current.toFixed(0)}%` : "--"} color={surv?.current != null && surv.current > 50 ? "text-emerald-400" : "text-red-400"}/>
            <Stat label="Buy/Sell" value={bs?.current != null ? bs.current.toFixed(2) : "--"} color={bs?.current != null && bs.current > 1 ? "text-emerald-400" : "text-red-400"}/>
          </div>
        </Panel>
      </div>

      {/* ── Row 2: Performance | Launchpads ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3">
        <Panel className="p-4" delay={0.2}>
          <Label tip="Peak market cap distribution for graduated tokens. Shows what to expect if you launch now.">Launch Performance</Label>
          {tiers ? <>
            <PerfRow label="Best 24h" value={tiers.best24h} max={tiers.best24h} time={tiers.time_to_peak?.best24h??null} color="text-amber-400"/>
            <PerfRow label="Top 10%" value={tiers.top10} max={tiers.best24h} time={tiers.time_to_peak?.top10??null} color="text-blue-400"/>
            <PerfRow label="Bonded" value={tiers.bonded} max={tiers.best24h} time={tiers.time_to_peak?.bonded??null} color="text-white/70"/>
            {tiers.all_median!=null && <PerfRow label="All" value={tiers.all_median} max={tiers.best24h} time={null} color="text-red-400/70"/>}
            {tiers.best_address && <div className="mt-2 text-[9px] text-white/20">
              <span className="font-mono">{tiers.best_address.slice(0,6)}...{tiers.best_address.slice(-4)}</span>{" "}
              <a href={`https://dexscreener.com/solana/${tiers.best_address}`} target="_blank" rel="noopener noreferrer" className="text-amber-400/40 hover:text-amber-400 underline">DexScreener</a>
            </div>}
          </> : <div className="text-white/20 text-[10px] py-4">Loading...</div>}
        </Panel>
        <Panel className="p-4" delay={0.25}>
          <Label tip="Token launches per platform from Dune on-chain data. Shows which launchpads are most active.">Launchpad Activity</Label>
          <div className="flex items-baseline gap-4 mb-3">
            <div className="text-xl font-black text-white"><Counter value={launches}/></div>
            {graduated!=null && graduated>0 && <div className="text-sm font-bold text-emerald-400"><Counter value={graduated}/><span className="text-[9px] text-white/20 ml-1 font-normal">graduated</span></div>}
            {gradRate!=null && <div className="text-sm font-bold text-amber-400">{gradRate.toFixed(1)}%</div>}
          </div>
          <div className="space-y-0.5">
            {sorted.slice(0,5).map(([k,v],i)=><LPBar key={k} name={k} value={v} max={maxLP} color={BAR_COLS[i%BAR_COLS.length]}/>)}
          </div>
        </Panel>
      </div>

      {/* ── Row 3: Narratives | Runners ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-3">
        <div>
          <Label tip="AI-classified token themes from trending DexScreener data. Click a narrative to see all tokens in it.">Trending Narratives</Label>
          <div className="text-[8px] text-red-400/30 mb-2">Includes unverified tokens for narrative identification. Not investment advice.</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-2">
            {narr?.narratives.map((nr,i)=><NarrCard key={nr.name} n={nr} i={i} onClick={()=>nav(`/narrative/${encodeURIComponent(nr.name)}`)}/>)}
          </div>
          {(!narr || narr.narratives.length===0) && <div className="text-white/20 text-center py-8 text-[10px]">Scanning narratives...</div>}
        </div>
        <div>
          <Label tip="Top tokens by percentage gain in the last 24 hours. DS links to DexScreener.">Top Runners</Label>
          <Panel className="p-3" delay={0.3}>
            {narr?.top_runners.map((t,i)=><Runner key={t.address} t={t} i={i}/>)}
            {(!narr || narr.top_runners.length===0) && <div className="text-white/20 text-center py-4 text-[9px]">No runners yet</div>}
          </Panel>
        </div>
      </div>
    </div>
  );
}
