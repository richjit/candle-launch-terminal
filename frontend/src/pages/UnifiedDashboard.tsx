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
const $ = (v:number) => v>=1e9?`$${(v/1e9).toFixed(1)}B`:v>=1e6?`$${(v/1e6).toFixed(1)}M`:v>=1e3?`$${(v/1e3).toFixed(1)}K`:`$${v.toFixed(0)}`;
const N = (v:number) => v>=1e6?`${(v/1e6).toFixed(1)}M`:v>=1e3?`${(v/1e3).toFixed(1)}K`:v.toLocaleString();
const P = (v:number|null) => v==null?"--":`${v>0?"+":""}${v.toFixed(0)}%`;
const T = (m:number|null) => {if(m==null)return"--";if(m<60)return`${Math.round(m)}m`;const h=Math.floor(m/60);if(h>=24){const d=Math.floor(h/24);return d>0&&h%24>0?`${d}d ${h%24}h`:`${d}d`;}return`${h}h`;};
const A = (c:string|null) => {if(!c)return"--";const h=Math.floor((Date.now()-new Date(c).getTime())/36e5);return h>=24?`${Math.floor(h/24)}d ago`:h>0?`${h}h ago`:`${Math.floor((Date.now()-new Date(c).getTime())/6e4)}m ago`;};

// ── Animated Counter ──
function Counter({value,d=700}:{value:number;d?:number}){
  const[v,setV]=useState(0);const p=useRef(0);
  useEffect(()=>{const s=p.current,e=value,t0=Date.now();const tick=()=>{const pr=Math.min((Date.now()-t0)/d,1);setV(Math.round(s+(e-s)*(1-Math.pow(1-pr,3))));if(pr<1)requestAnimationFrame(tick);};requestAnimationFrame(tick);p.current=value;},[value,d]);
  return<>{v.toLocaleString()}</>;
}

// ── Live Pulse ──
function Live(){return<span className="relative flex h-2 w-2"><span className="animate-ping absolute h-full w-full rounded-full bg-emerald-400 opacity-50"/><span className="relative rounded-full h-2 w-2 bg-emerald-400"/></span>;}

// ── Tooltip ──
function Tip({text}:{text:string}){
  const[s,set]=useState(false);
  return<span className="relative ml-1 inline-block">
    <button onMouseEnter={()=>set(true)} onMouseLeave={()=>set(false)} className="w-4 h-4 rounded-full border border-white/10 text-white/20 hover:text-white/50 hover:border-white/25 text-[9px] inline-flex items-center justify-center transition-all hover:bg-white/5">?</button>
    <AnimatePresence>{s&&<motion.div initial={{opacity:0,y:4}} animate={{opacity:1,y:0}} exit={{opacity:0}} className="absolute z-50 bottom-7 left-1/2 -translate-x-1/2 w-60 px-3 py-2.5 rounded-xl bg-[#1a1c2e]/95 backdrop-blur border border-white/10 text-[11px] text-white/60 leading-relaxed shadow-2xl pointer-events-none">{text}</motion.div>}</AnimatePresence>
  </span>;
}

// ── Health Gauge (large, prominent) ──
function Gauge({score}:{score:number}){
  const r=54,c=Math.PI*r,off=c*(1-score/100);
  const col=score>=70?"#00e676":score<=30?"#ff1744":"#f0b90b";
  const lab=score>=70?"Launch Window":score<=30?"Danger Zone":"Neutral";
  const msg=score>=70?"Conditions are favorable for launching":score<=30?"Market conditions are poor — consider waiting":"Market is stable — launch with caution";
  return(
    <div className="flex flex-col items-center">
      <svg width="130" height="75" viewBox="0 0 130 75">
        <path d="M 8 70 A 54 54 0 0 1 122 70" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth={5} strokeLinecap="round"/>
        <motion.path d="M 8 70 A 54 54 0 0 1 122 70" fill="none" stroke={col} strokeWidth={5} strokeLinecap="round"
          strokeDasharray={c} initial={{strokeDashoffset:c}} animate={{strokeDashoffset:off}}
          transition={{duration:1.5,ease:"easeOut"}} style={{filter:`drop-shadow(0 0 12px ${col}60)`}}/>
      </svg>
      <div className="-mt-9 text-center">
        <div className="text-4xl font-black" style={{color:col}}>{score.toFixed(0)}</div>
        <div className="text-[9px] font-bold uppercase tracking-[0.2em] mt-0.5" style={{color:`${col}bb`}}>{lab}</div>
        <div className="text-[10px] text-white/30 mt-1 max-w-[180px]">{msg}</div>
      </div>
    </div>
  );
}

// ── Condition Check (gamified) ──
function Check({label,value,good,unit=""}:{label:string;value:number|null;good:boolean;unit?:string}){
  if(value==null)return null;
  return(
    <div className={`flex items-center gap-2 py-1 ${good?"text-emerald-400":"text-red-400"}`}>
      <div className={`w-1.5 h-1.5 rounded-full ${good?"bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]":"bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.4)]"}`}/>
      <span className="text-[11px] text-white/50 flex-1">{label}</span>
      <span className="text-[12px] font-bold tabular-nums">{typeof value==="number"&&value>1000?N(value):value.toFixed(value<10?2:0)}{unit}</span>
    </div>
  );
}

// ── Performance Tier Row ──
function TierRow({label,value,max,time,rank}:{label:string;value:number;max:number;time:number|null;rank:number}){
  const w=Math.max(4,(Math.log10(value+1)/Math.log10(max+1))*100);
  const colors=["text-amber-400","text-blue-400","text-white/60","text-red-400/60"];
  const barColors=["#f0b90b","#60a5fa","#9ca3af","#f87171"];
  return(
    <div className="flex items-center gap-2 py-1.5">
      <span className={`text-[11px] w-16 font-medium ${colors[rank]||colors[3]}`}>{label}</span>
      <div className="flex-1 h-1 rounded-full bg-white/[0.03] overflow-hidden">
        <motion.div initial={{width:0}} animate={{width:`${w}%`}} transition={{duration:0.8,delay:rank*0.1,ease:"easeOut"}}
          className="h-full rounded-full" style={{background:barColors[rank]||barColors[3]}}/>
      </div>
      <span className={`text-[12px] font-bold tabular-nums w-16 text-right ${colors[rank]||colors[3]}`}>{$(value)}</span>
      <span className="text-[10px] text-white/15 w-10 text-right tabular-nums">{T(time)}</span>
    </div>
  );
}

// ── Launchpad Bar ──
const LP:Record<string,string> = {pumpdotfun:"pump.fun",letsbonk:"LetsBonk",bags:"Bags",moonshot:"Moonshot",jupstudio:"Jup Studio",launchlab:"LaunchLab"};
const BC=["#f0b90b","#34d399","#60a5fa","#c084fc","#f472b6"];

// ── Narrative Card (redesigned with heat) ──
const LC_GRAD:Record<string,string> = {
  emerging:"from-blue-500/20 via-blue-500/5 to-transparent",
  trending:"from-emerald-500/20 via-emerald-500/5 to-transparent",
  saturated:"from-amber-500/15 via-amber-500/5 to-transparent",
  fading:"from-red-500/10 via-transparent to-transparent",
};
const LC_BORDER:Record<string,string> = {
  emerging:"border-blue-500/25 hover:border-blue-400/40",
  trending:"border-emerald-500/25 hover:border-emerald-400/40",
  saturated:"border-amber-500/20 hover:border-amber-400/35",
  fading:"border-red-500/15 hover:border-red-400/25",
};
const LC_BADGE:Record<string,string> = {
  emerging:"bg-blue-500/20 text-blue-300",trending:"bg-emerald-500/20 text-emerald-300",
  saturated:"bg-amber-500/15 text-amber-300",fading:"bg-red-500/15 text-red-300",
};

function NarrCard({nr,i,onClick}:{nr:NarrativeData;i:number;onClick:()=>void}){
  const heat = nr.avg_gain_pct > 100 ? 3 : nr.avg_gain_pct > 30 ? 2 : nr.avg_gain_pct > 0 ? 1 : 0;
  return(
    <motion.button onClick={onClick} initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{delay:0.1+i*0.05,duration:0.3}}
      className={`bg-gradient-to-br ${LC_GRAD[nr.lifecycle]||LC_GRAD.fading} border ${LC_BORDER[nr.lifecycle]||LC_BORDER.fading} rounded-xl p-4 text-left hover:scale-[1.02] active:scale-[0.98] transition-all w-full group relative overflow-hidden`}>
      {/* Heat flames */}
      {heat >= 2 && <div className="absolute top-2 right-2 text-[14px] opacity-60">{heat >= 3 ? "🔥🔥" : "🔥"}</div>}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[15px] font-bold text-white/90 group-hover:text-white">{nr.name}</span>
        <span className={`text-[8px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${LC_BADGE[nr.lifecycle]||LC_BADGE.fading}`}>{nr.lifecycle}</span>
      </div>
      <div className="flex items-center gap-4 text-[11px]">
        <span className="text-white/40"><span className="text-white/70 font-semibold">{nr.token_count}</span> tokens</span>
        <span className="text-white/40">{$(nr.total_volume)} vol</span>
        <span className={`font-bold ${nr.avg_gain_pct>0?"text-emerald-400":"text-red-400"}`}>{P(nr.avg_gain_pct)}</span>
      </div>
    </motion.button>
  );
}

// ── Runner Row (leaderboard style) ──
function RunnerRow({t,i}:{t:NarrativeTokenData;i:number}){
  const up=(t.price_change_pct??0)>0;
  const medals=["🥇","🥈","🥉"];
  return(
    <motion.div initial={{opacity:0,x:10}} animate={{opacity:1,x:0}} transition={{delay:0.15+i*0.04,duration:0.2}}
      className="flex items-center gap-2.5 py-2 border-b border-white/[0.04] last:border-0 group hover:bg-white/[0.02] transition-colors rounded px-1 -mx-1">
      <span className="text-[12px] w-5 text-center">{i<3?medals[i]:<span className="text-white/15 text-[10px]">#{i+1}</span>}</span>
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-semibold text-white/80 group-hover:text-white truncate">{t.name}</div>
        <div className="text-[9px] text-white/25 flex items-center gap-1">
          {t.narrative&&<span className="text-amber-400/50">{t.narrative}</span>}
          <span>·</span>
          <span>{A(t.created_at)}</span>
        </div>
      </div>
      <div className={`text-[11px] font-bold tabular-nums px-2 py-0.5 rounded-md ${up?"bg-emerald-500/15 text-emerald-400":"bg-red-500/15 text-red-400"}`}>
        {P(t.price_change_pct)}
      </div>
      <span className="text-[10px] tabular-nums text-white/20 w-14 text-right">{t.mcap?$(t.mcap):"--"}</span>
      <a href={`https://dexscreener.com/solana/${t.address}`} target="_blank" rel="noopener noreferrer"
        onClick={e=>e.stopPropagation()} className="opacity-0 group-hover:opacity-100 transition-opacity">
        <img src="https://dexscreener.com/favicon.ico" alt="DexScreener" className="w-3.5 h-3.5 rounded-sm"/>
      </a>
    </motion.div>
  );
}

// ── Glass Panel ──
function G({children,className="",delay=0}:{children:React.ReactNode;className?:string;delay?:number}){
  return<motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{delay,duration:0.35}}
    className={`bg-white/[0.02] backdrop-blur-sm border border-white/[0.06] rounded-2xl ${className}`}>{children}</motion.div>;
}

// ══════════════════════════════════════════════════════════════
export default function UnifiedDashboard(){
  const nav=useNavigate();
  const cRef=useRef<CandlestickChartHandle>(null);
  const rSet=useRef(false);

  const[chart,setChart]=useState<ChartData|null>(null);
  const{data:launch}=useApiPolling<LaunchOverviewData>("/launch/overview?range=30d",60000);
  const{data:narr}=useApiPolling<NarrativeOverview>("/narrative/overview",60000);

  useEffect(()=>{
    const x=["dex_volume","stablecoin_supply","vol_regime","new_wallets","priority_fees"];
    fetchChart("all",x).then(setChart).catch(()=>{});
    const iv=setInterval(async()=>{try{const d=await fetchChart("all",x);setChart(p=>{if(!p||d.candles.length!==p.candles.length)return d;if(d.candles[d.candles.length-1]?.close!==p.candles[p.candles.length-1]?.close)return d;return p;});}catch{}},60000);
    return()=>clearInterval(iv);
  },[]);

  useEffect(()=>{
    if(!chart||rSet.current)return;
    const t=setTimeout(()=>{cRef.current?.getChart()?.timeScale().fitContent();rSet.current=true;},500);
    return()=>clearTimeout(t);
  },[chart]);

  const score=chart?.scores?.length?chart.scores[chart.scores.length-1].score:null;
  const tiers=launch?.metrics.find(m=>m.name==="Launch Performance")?.tiers;
  const act=launch?.metrics.find(m=>m.name==="Launchpad Activity");
  const launches=act?.current??0;
  const gradRate=(act as any)?.migration_rate as number|undefined;
  const graduated=(act as any)?.total_graduated as number|undefined;
  const bd=(act?.breakdown||{}) as Record<string,number>;
  const surv=launch?.metrics.find(m=>m.name==="Survival Rate (24h)");
  const bs=launch?.metrics.find(m=>m.name==="Buy/Sell Ratio");
  const vol=launch?.metrics.find(m=>m.name==="Volume");
  const sorted=Object.entries(bd).filter(([k,v])=>v>0&&k!=="moon.it").sort((a,b)=>b[1]-a[1]);
  const maxLP=sorted[0]?.[1]||1;

  return(
    <div className="w-full min-h-screen -m-6 p-5 relative overflow-hidden">
      {/* Background */}
      <div className="fixed inset-0 pointer-events-none -z-10">
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] bg-purple-900/[0.06] rounded-full blur-[140px]"/>
        <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] bg-cyan-900/[0.04] rounded-full blur-[140px]"/>
        <div className="absolute inset-0" style={{backgroundImage:"radial-gradient(rgba(255,255,255,0.02) 1px, transparent 1px)",backgroundSize:"28px 28px"}}/>
      </div>

      {/* ── Header ── */}
      <motion.div initial={{opacity:0}} animate={{opacity:1}} className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <span className="text-amber-400 font-black text-lg tracking-[0.3em]">CANDLE</span>
          <Live/>
          <span className="text-[10px] text-white/15 ml-2">Solana Launch Intelligence</span>
        </div>
        <Tip text="Real-time dashboard for Solana token developers. Health score tells you if it's a good time to launch. Launch conditions show market performance. Narratives show what themes are trending."/>
      </motion.div>

      {/* ── Row 1: Health + Chart + Conditions ── */}
      <div className="grid grid-cols-[160px_1fr_220px] gap-3 mb-3" style={{height:"195px"}}>
        {/* Health */}
        <G className="p-4 flex items-center justify-center" delay={0.05}>
          {score!==null?<Gauge score={score}/>:<div className="text-white/15 text-xs animate-pulse">Calculating...</div>}
        </G>

        {/* Chart */}
        <G className="!p-0 overflow-hidden" delay={0.1}>
          {chart&&chart.candles.length>0?(
            <CandlestickChart ref={cRef} candles={chart.candles} scores={chart.scores} height={191}/>
          ):<div className="h-full flex items-center justify-center text-white/15 text-xs animate-pulse">Loading SOL chart...</div>}
        </G>

        {/* Conditions checklist */}
        <G className="p-4" delay={0.15}>
          <div className="text-[9px] text-white/25 uppercase tracking-[0.15em] font-semibold mb-2">Market Conditions</div>
          <Check label="24h Launches" value={launches} good={launches>10000}/>
          <Check label="Graduation Rate" value={gradRate??null} good={(gradRate??0)>1} unit="%"/>
          <Check label="24h Survival" value={surv?.current??null} good={(surv?.current??0)>20} unit="%"/>
          <Check label="Buy/Sell Ratio" value={bs?.current??null} good={(bs?.current??0)>0.8}/>
          <Check label="DEX Volume" value={vol?.current??null} good={(vol?.current??0)>1e9}/>
          {graduated!=null&&<Check label="Graduated" value={graduated} good={graduated>100}/>}
        </G>
      </div>

      {/* ── Row 2: Performance + Launchpads ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3">
        <G className="p-4" delay={0.2}>
          <div className="flex items-center gap-1 mb-2">
            <span className="text-[9px] text-white/25 uppercase tracking-[0.15em] font-semibold">Launch Performance</span>
            <Tip text="Peak market cap tiers for tokens that graduated from bonding curves in the last 24 hours."/>
          </div>
          {tiers?<>
            <TierRow label="Best (24h)" value={tiers.best24h} max={tiers.best24h} time={tiers.time_to_peak?.best24h??null} rank={0}/>
            <TierRow label="Top 10%" value={tiers.top10} max={tiers.best24h} time={tiers.time_to_peak?.top10??null} rank={1}/>
            <TierRow label="Bonded" value={tiers.bonded} max={tiers.best24h} time={tiers.time_to_peak?.bonded??null} rank={2}/>
            {tiers.all_median!=null&&<TierRow label="All Launches" value={tiers.all_median} max={tiers.best24h} time={null} rank={3}/>}
            {tiers.best_address&&<div className="mt-2 flex items-center gap-2 text-[9px] text-white/20">
              <span className="font-mono">{tiers.best_address.slice(0,6)}...{tiers.best_address.slice(-4)}</span>
              <a href={`https://dexscreener.com/solana/${tiers.best_address}`} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-amber-400/40 hover:text-amber-400 transition-colors">
                <img src="https://dexscreener.com/favicon.ico" alt="" className="w-3 h-3 rounded-sm"/> DexScreener
              </a>
            </div>}
          </>:<div className="text-white/15 text-[10px] py-6 animate-pulse">Loading performance data...</div>}
        </G>

        <G className="p-4" delay={0.25}>
          <div className="flex items-center gap-1 mb-2">
            <span className="text-[9px] text-white/25 uppercase tracking-[0.15em] font-semibold">Launchpad Activity</span>
            <Tip text="Token launches per platform. Data from Dune Analytics on-chain queries, refreshed every 6 hours."/>
          </div>
          <div className="flex items-baseline gap-5 mb-3">
            <div><span className="text-2xl font-black text-white"><Counter value={launches}/></span><span className="text-[10px] text-white/20 ml-1.5">launches</span></div>
            {graduated!=null&&graduated>0&&<div><span className="text-base font-bold text-emerald-400"><Counter value={graduated}/></span><span className="text-[9px] text-white/15 ml-1">graduated</span></div>}
            {gradRate!=null&&<span className="text-base font-bold text-amber-400">{gradRate.toFixed(1)}%</span>}
          </div>
          <div className="space-y-1">
            {sorted.slice(0,5).map(([k,v],i)=>(
              <div key={k} className="flex items-center gap-2 py-0.5">
                <span className="text-[10px] text-white/40 w-16 truncate">{LP[k]||k}</span>
                <div className="flex-1 h-1.5 rounded-full bg-white/[0.03] overflow-hidden">
                  <motion.div initial={{width:0}} animate={{width:`${Math.max(2,(v/maxLP)*100)}%`}}
                    transition={{duration:0.6,delay:0.3+i*0.08,ease:"easeOut"}}
                    className="h-full rounded-full" style={{background:BC[i%BC.length]}}/>
                </div>
                <span className="text-[10px] tabular-nums text-white/25 w-14 text-right">{v.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </G>
      </div>

      {/* ── Row 3: Narratives + Runners ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-3">
        {/* Narratives */}
        <div>
          <div className="flex items-center gap-1 mb-2">
            <span className="text-[9px] text-white/25 uppercase tracking-[0.15em] font-semibold">What to Launch</span>
            <Tip text="AI-classified token narratives from DexScreener trending data. Shows which themes have momentum right now. Click to explore tokens in each narrative."/>
          </div>
          <div className="text-[8px] text-red-400/30 mb-2">Includes unverified tokens for narrative identification only. Not investment advice.</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2.5">
            {narr?.narratives.map((nr,i)=><NarrCard key={nr.name} nr={nr} i={i} onClick={()=>nav(`/narrative/${encodeURIComponent(nr.name)}`)}/>)}
          </div>
          {(!narr||narr.narratives.length===0)&&<G className="p-8 text-center" delay={0.3}><div className="text-white/15 text-sm animate-pulse">Scanning for trending narratives...</div></G>}
        </div>

        {/* Runners */}
        <div>
          <div className="flex items-center gap-1 mb-2">
            <span className="text-[9px] text-white/25 uppercase tracking-[0.15em] font-semibold">Top Runners</span>
            <Tip text="Leaderboard of tokens with highest percentage gain in the last 24 hours. Hover for DexScreener link."/>
          </div>
          <G className="p-3" delay={0.3}>
            {narr?.top_runners.map((t,i)=><RunnerRow key={t.address} t={t} i={i}/>)}
            {(!narr||narr.top_runners.length===0)&&<div className="text-white/15 text-center py-8 text-[10px] animate-pulse">Scanning runners...</div>}
          </G>
        </div>
      </div>
    </div>
  );
}
