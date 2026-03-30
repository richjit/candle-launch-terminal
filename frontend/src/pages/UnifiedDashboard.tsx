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
const $=(v:number)=>v>=1e9?`$${(v/1e9).toFixed(1)}B`:v>=1e6?`$${(v/1e6).toFixed(1)}M`:v>=1e3?`$${(v/1e3).toFixed(1)}K`:`$${v.toFixed(0)}`;
const N=(v:number)=>v>=1e6?`${(v/1e6).toFixed(1)}M`:v>=1e3?`${(v/1e3).toFixed(1)}K`:v.toLocaleString();
const P=(v:number|null)=>v==null?"--":`${v>0?"+":""}${v.toFixed(0)}%`;
const T=(m:number|null)=>{if(m==null)return"--";if(m<60)return`${Math.round(m)}m`;const h=Math.floor(m/60);if(h>=24){const d=Math.floor(h/24);return d>0&&h%24>0?`${d}d ${h%24}h`:`${d}d`;}return`${h}h`;};
const A=(c:string|null)=>{if(!c)return"";const h=Math.floor((Date.now()-new Date(c).getTime())/36e5);return h>=24?`${Math.floor(h/24)}d ago`:h>0?`${h}h ago`:`${Math.floor((Date.now()-new Date(c).getTime())/6e4)}m ago`;};

// ── Animated Counter ──
function Counter({value,d=700}:{value:number;d?:number}){
  const[v,setV]=useState(0);const p=useRef(0);
  useEffect(()=>{const s=p.current,e=value,t0=Date.now();const tick=()=>{const pr=Math.min((Date.now()-t0)/d,1);setV(Math.round(s+(e-s)*(1-Math.pow(1-pr,3))));if(pr<1)requestAnimationFrame(tick);};requestAnimationFrame(tick);p.current=value;},[value,d]);
  return<>{v.toLocaleString()}</>;
}

// ── Components ──
function Live(){return<span className="relative flex h-2 w-2"><span className="animate-ping absolute h-full w-full rounded-full bg-emerald-400 opacity-50"/><span className="relative rounded-full h-2 w-2 bg-emerald-400"/></span>;}

function InfoIcon({text}:{text:string}){
  const[s,set]=useState(false);
  return<span className="relative inline-flex ml-1.5 align-middle">
    <button onMouseEnter={()=>set(true)} onMouseLeave={()=>set(false)}
      className="text-white/10 hover:text-white/30 transition-colors"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg></button>
    <AnimatePresence>{s&&<motion.div initial={{opacity:0,y:4}} animate={{opacity:1,y:0}} exit={{opacity:0}}
      className="absolute z-50 bottom-7 left-1/2 -translate-x-1/2 w-56 px-3 py-2 rounded-xl bg-[#1a1c2e]/95 backdrop-blur border border-white/10 text-[10px] text-white/60 leading-relaxed shadow-2xl pointer-events-none">{text}</motion.div>}</AnimatePresence>
  </span>;
}

function Gauge({score}:{score:number}){
  const r=54,c=Math.PI*r,off=c*(1-score/100);
  const col=score>=70?"#00e676":score<=30?"#ff1744":"#f0b90b";
  const lab=score>=70?"Launch Window":score<=30?"Danger Zone":"Neutral";
  const msg=score>=70?"Favorable conditions":score<=30?"Consider waiting":"Proceed with caution";
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
        <div className="text-[10px] text-white/30 mt-1">{msg}</div>
      </div>
    </div>
  );
}

function Check({label,value,good,display}:{label:string;value:number|null;good:boolean;display:string}){
  if(value==null)return null;
  return(
    <div className="flex items-center gap-2 py-0.5">
      <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${good?"bg-emerald-400 shadow-[0_0_4px_rgba(52,211,153,0.5)]":"bg-red-400 shadow-[0_0_4px_rgba(248,113,113,0.4)]"}`}/>
      <span className="text-[11px] text-white/40 flex-1">{label}</span>
      <span className={`text-[11px] font-bold tabular-nums ${good?"text-emerald-400":"text-red-400"}`}>{display}</span>
    </div>
  );
}

function G({children,className="",delay=0}:{children:React.ReactNode;className?:string;delay?:number}){
  return<motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{delay,duration:0.35}}
    className={`bg-white/[0.02] backdrop-blur-sm border border-white/[0.06] rounded-2xl ${className}`}>{children}</motion.div>;
}

// ── Lifecycle styles ──
const LC_GRAD:Record<string,string>={emerging:"from-blue-500/15 to-transparent",trending:"from-emerald-500/15 to-transparent",saturated:"from-amber-500/10 to-transparent",fading:"from-red-500/8 to-transparent"};
const LC_BORDER:Record<string,string>={emerging:"border-blue-500/20 hover:border-blue-400/35",trending:"border-emerald-500/20 hover:border-emerald-400/35",saturated:"border-amber-500/15 hover:border-amber-400/30",fading:"border-red-500/10 hover:border-red-400/20"};
const LC_BADGE:Record<string,string>={emerging:"bg-blue-500/20 text-blue-300",trending:"bg-emerald-500/20 text-emerald-300",saturated:"bg-amber-500/15 text-amber-300",fading:"bg-red-500/15 text-red-300"};

const LP:Record<string,string>={pumpdotfun:"pump.fun",letsbonk:"LetsBonk",bags:"Bags",moonshot:"Moonshot",jupstudio:"Jup Studio",launchlab:"LaunchLab"};
const BC=["#f0b90b","#34d399","#60a5fa","#c084fc","#f472b6"];

const DS_ICON = "https://dd.dexscreener.com/ds-data/dapps/dexscreener.png";

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

  // Data
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
        <div className="absolute inset-0" style={{backgroundImage:"radial-gradient(rgba(255,255,255,0.015) 1px, transparent 1px)",backgroundSize:"28px 28px"}}/>
      </div>

      {/* ── Header ── */}
      <motion.div initial={{opacity:0}} animate={{opacity:1}} className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <span className="text-amber-400 font-black text-lg tracking-[0.3em]">CANDLE</span>
          <Live/>
          <span className="text-[10px] text-white/15 ml-2">Solana Launch Intelligence</span>
        </div>
        <InfoIcon text="Real-time dashboard for Solana token developers. The health score tells you if conditions are right for launching. Below, see what tokens are achieving and which narratives are trending."/>
      </motion.div>

      {/* ── Row 1: Gauge | Chart | Conditions ── */}
      <div className="grid grid-cols-[160px_1fr_220px] gap-3 mb-3" style={{height:"200px"}}>
        <G className="p-4 flex items-center justify-center" delay={0.05}>
          {score!==null?<Gauge score={score}/>:<div className="text-white/15 text-xs animate-pulse">Calculating...</div>}
        </G>
        <G className="!p-0 overflow-hidden" delay={0.1}>
          {chart&&chart.candles.length>0?(
            <CandlestickChart ref={cRef} candles={chart.candles} scores={chart.scores} height={196}/>
          ):<div className="h-full flex items-center justify-center text-white/15 text-xs animate-pulse">Loading SOL chart...</div>}
        </G>
        <G className="p-4 flex flex-col justify-center" delay={0.15}>
          <div className="text-xs text-white/50 uppercase tracking-[0.12em] font-bold mb-2">Market Conditions</div>
          <Check label="24h Launches" value={launches} good={launches>10000} display={N(launches)}/>
          <Check label="Graduation Rate" value={gradRate??null} good={(gradRate??0)>1} display={`${(gradRate??0).toFixed(1)}%`}/>
          <Check label="24h Survival" value={surv?.current??null} good={(surv?.current??0)>20} display={`${(surv?.current??0).toFixed(0)}%`}/>
          <Check label="Buy/Sell Ratio" value={bs?.current??null} good={(bs?.current??0)>0.8} display={(bs?.current??0).toFixed(2)}/>
          <Check label="DEX Volume" value={vol?.current??null} good={(vol?.current??0)>1e9} display={$(vol?.current??0)}/>
        </G>
      </div>

      {/* ── Row 2: Performance | Launchpads ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3">
        {/* Launch Performance — DexScreener link INLINE with Best row */}
        <G className="p-4" delay={0.2}>
          <div className="flex items-center gap-1 mb-3">
            <span className="text-xs text-white/50 uppercase tracking-[0.12em] font-bold">Launch Performance</span>
            <InfoIcon text="Peak market cap that graduated tokens reached. 'Peaked after' shows how long from launch to ATH."/>
          </div>
          {tiers?<div className="space-y-1">
            {/* Column headers */}
            <div className="flex items-center gap-2 text-[8px] text-white/15 uppercase tracking-wider mb-1">
              <span className="w-20"/>
              <span className="flex-1"/>
              <span className="w-16 text-right">Peak Mcap</span>
              <span className="w-16 text-right">Peaked after</span>
            </div>
            {/* Best (24h) — with DexScreener link right here */}
            <div className="flex items-center gap-2 py-1">
              <span className="text-[11px] w-20 text-amber-400 font-medium">Best (24h)</span>
              <div className="flex-1 h-1 rounded-full bg-white/[0.03] overflow-hidden"><motion.div initial={{width:0}} animate={{width:"100%"}} transition={{duration:0.8}} className="h-full rounded-full bg-amber-400"/></div>
              <span className="text-[12px] font-bold tabular-nums w-16 text-right text-amber-400">{$(tiers.best24h)}</span>
              <span className="text-[10px] text-white/20 w-16 text-right tabular-nums">{T(tiers.time_to_peak?.best24h??null)}</span>
            </div>
            {tiers.best_address&&<div className="flex items-center gap-2 ml-20 -mt-0.5 mb-1">
              <span className="text-[9px] font-mono text-white/20">{tiers.best_address.slice(0,6)}...{tiers.best_address.slice(-4)}</span>
              <a href={`https://dexscreener.com/solana/${tiers.best_address}`} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-[9px] text-amber-400/40 hover:text-amber-400 transition-colors">
                <img src={DS_ICON} alt="" className="w-3.5 h-3.5 rounded" onError={e=>{(e.target as HTMLImageElement).style.display='none'}}/>
                <span>DexScreener</span>
              </a>
            </div>}
            {/* Top 10% */}
            <div className="flex items-center gap-2 py-1">
              <span className="text-[11px] w-20 text-blue-400 font-medium">Top 10%</span>
              <div className="flex-1 h-1 rounded-full bg-white/[0.03] overflow-hidden"><motion.div initial={{width:0}} animate={{width:`${Math.max(4,(Math.log10(tiers.top10+1)/Math.log10(tiers.best24h+1))*100)}%`}} transition={{duration:0.8,delay:0.1}} className="h-full rounded-full bg-blue-400"/></div>
              <span className="text-[12px] font-bold tabular-nums w-16 text-right text-blue-400">{$(tiers.top10)}</span>
              <span className="text-[10px] text-white/20 w-16 text-right tabular-nums">{T(tiers.time_to_peak?.top10??null)}</span>
            </div>
            {/* Bonded */}
            <div className="flex items-center gap-2 py-1">
              <span className="text-[11px] w-20 text-white/60 font-medium">Bonded</span>
              <div className="flex-1 h-1 rounded-full bg-white/[0.03] overflow-hidden"><motion.div initial={{width:0}} animate={{width:`${Math.max(4,(Math.log10(tiers.bonded+1)/Math.log10(tiers.best24h+1))*100)}%`}} transition={{duration:0.8,delay:0.2}} className="h-full rounded-full bg-white/40"/></div>
              <span className="text-[12px] font-bold tabular-nums w-16 text-right text-white/60">{$(tiers.bonded)}</span>
              <span className="text-[10px] text-white/20 w-16 text-right tabular-nums">{T(tiers.time_to_peak?.bonded??null)}</span>
            </div>
            {/* All */}
            {tiers.all_median!=null&&<div className="flex items-center gap-2 py-1 mt-1 border-t border-white/[0.04]">
              <span className="text-[11px] w-20 text-red-400/60 font-medium">All Launches</span>
              <div className="flex-1 h-1 rounded-full bg-white/[0.03] overflow-hidden"><motion.div initial={{width:0}} animate={{width:`${Math.max(3,(Math.log10(tiers.all_median+1)/Math.log10(tiers.best24h+1))*100)}%`}} transition={{duration:0.8,delay:0.3}} className="h-full rounded-full bg-red-400/50"/></div>
              <span className="text-[12px] font-bold tabular-nums w-16 text-right text-red-400/60">{$(tiers.all_median)}</span>
              <span className="w-16"/>
            </div>}
          </div>:<div className="text-white/15 text-[10px] py-6 animate-pulse text-center">Loading...</div>}
        </G>

        {/* Launchpad Activity — NO duplicate stats, just the per-platform bars */}
        <G className="p-4" delay={0.25}>
          <div className="flex items-center gap-1 mb-3">
            <span className="text-xs text-white/50 uppercase tracking-[0.12em] font-bold">Launchpad Activity</span>
            <InfoIcon text="Token launches per platform from Dune on-chain data. Shows which launchpads developers are using most."/>
          </div>
          <div className="space-y-1.5">
            {sorted.slice(0,5).map(([k,v],i)=>(
              <div key={k} className="flex items-center gap-2">
                <span className="text-[11px] text-white/50 w-16 truncate font-medium">{LP[k]||k}</span>
                <div className="flex-1 h-2 rounded-full bg-white/[0.03] overflow-hidden">
                  <motion.div initial={{width:0}} animate={{width:`${Math.max(3,(v/maxLP)*100)}%`}}
                    transition={{duration:0.7,delay:0.3+i*0.08,ease:"easeOut"}}
                    className="h-full rounded-full" style={{background:BC[i%BC.length]}}/>
                </div>
                <span className="text-[11px] tabular-nums text-white/30 w-14 text-right font-medium">{v.toLocaleString()}</span>
              </div>
            ))}
          </div>
          {graduated!=null&&<div className="mt-3 pt-2 border-t border-white/[0.04] flex items-center gap-4 text-[10px] text-white/25">
            <span><span className="text-emerald-400 font-bold">{N(graduated)}</span> graduated</span>
            {gradRate!=null&&<span><span className="text-amber-400 font-bold">{gradRate.toFixed(1)}%</span> graduation rate</span>}
          </div>}
        </G>
      </div>

      {/* ── Row 3: Narratives + Runners ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-3">
        {/* Narratives */}
        <div>
          <div className="flex items-center gap-1 mb-1">
            <span className="text-xs text-white/50 uppercase tracking-[0.12em] font-bold">What to Launch</span>
            <InfoIcon text="AI-classified trending token themes. Narratives with momentum are marked Trending. Fire icons show high average gains. Click to explore tokens."/>
          </div>
          <div className="text-[8px] text-red-400/25 mb-2">Includes unverified tokens for narrative identification. Not investment advice.</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2.5">
            {narr?.narratives.map((nr,i)=>{
              const heat=nr.avg_gain_pct>100?3:nr.avg_gain_pct>30?2:nr.avg_gain_pct>0?1:0;
              return(
                <motion.button key={nr.name} onClick={()=>nav(`/narrative/${encodeURIComponent(nr.name)}`)}
                  initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{delay:0.1+i*0.05,duration:0.3}}
                  className={`bg-gradient-to-br ${LC_GRAD[nr.lifecycle]||LC_GRAD.fading} border ${LC_BORDER[nr.lifecycle]||LC_BORDER.fading} rounded-xl p-4 text-left hover:scale-[1.02] active:scale-[0.98] transition-all w-full group relative overflow-hidden`}>
                  {heat>=2&&<div className="absolute top-2 right-2 text-sm opacity-50">{heat>=3?"🔥🔥":"🔥"}</div>}
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-bold text-white/90 group-hover:text-white">{nr.name}</span>
                    <span className={`text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full ${LC_BADGE[nr.lifecycle]||LC_BADGE.fading}`}>{nr.lifecycle}</span>
                  </div>
                  <div className="flex items-center gap-3 text-[10px]">
                    <span className="text-white/40"><span className="text-white/60 font-semibold">{nr.token_count}</span> tokens</span>
                    <span className="text-white/30">{$(nr.total_volume)}</span>
                    <span className={`font-bold ${nr.avg_gain_pct>0?"text-emerald-400":"text-red-400"}`}>{P(nr.avg_gain_pct)}</span>
                  </div>
                </motion.button>
              );
            })}
          </div>
          {(!narr||narr.narratives.length===0)&&<G className="p-8 text-center" delay={0.3}><div className="text-white/15 text-sm animate-pulse">Scanning for trending narratives...</div></G>}
        </div>

        {/* Runners — capped height with scroll */}
        <div>
          <div className="flex items-center gap-1 mb-2">
            <span className="text-xs text-white/50 uppercase tracking-[0.12em] font-bold">Top Runners</span>
            <InfoIcon text="Tokens with highest gains in 24h. Hover a row to see the DexScreener link."/>
          </div>
          <G className="p-3 max-h-[400px] overflow-y-auto" delay={0.3}>
            {narr?.top_runners.slice(0,10).map((t,i)=>{
              const up=(t.price_change_pct??0)>0;
              const medals=["🥇","🥈","🥉"];
              return(
                <motion.div key={t.address} initial={{opacity:0,x:8}} animate={{opacity:1,x:0}} transition={{delay:0.15+i*0.04,duration:0.2}}
                  className="flex items-center gap-2 py-2 border-b border-white/[0.04] last:border-0 group hover:bg-white/[0.02] transition-colors rounded px-1 -mx-1">
                  <span className="text-xs w-5 text-center">{i<3?medals[i]:<span className="text-white/15 text-[10px]">#{i+1}</span>}</span>
                  <div className="flex-1 min-w-0">
                    <a href={`https://dexscreener.com/solana/${t.address}`} target="_blank" rel="noopener noreferrer"
                      onClick={e=>e.stopPropagation()} className="text-[12px] font-semibold text-white/80 hover:text-amber-400 transition-colors truncate block">{t.name}</a>
                    <div className="text-[9px] text-white/25">
                      {t.narrative&&<span className="text-amber-400/50">{t.narrative}</span>}
                      {t.narrative&&<span className="mx-1">·</span>}
                      {A(t.created_at)}
                    </div>
                  </div>
                  <div className={`text-[11px] font-bold tabular-nums px-2 py-0.5 rounded-md ${up?"bg-emerald-500/15 text-emerald-400":"bg-red-500/15 text-red-400"}`}>
                    {P(t.price_change_pct)}
                  </div>
                  <span className="text-[10px] tabular-nums text-white/20 w-14 text-right">{t.mcap?$(t.mcap):"--"}</span>
                </motion.div>
              );
            })}
            {(!narr||narr.top_runners.length===0)&&<div className="text-white/15 text-center py-6 text-[10px] animate-pulse">Scanning runners...</div>}
          </G>
        </div>
      </div>
    </div>
  );
}
