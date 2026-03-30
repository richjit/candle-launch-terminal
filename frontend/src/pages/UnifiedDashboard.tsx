import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import CandlestickChart, { type CandlestickChartHandle } from "../components/charts/CandlestickChart";
import LaunchPerformanceCard from "../components/launch/LaunchPerformanceCard";
import LaunchMigrationCard from "../components/launch/LaunchMigrationCard";
import LaunchMetricCard from "../components/launch/LaunchMetricCard";
import { useApiPolling } from "../hooks/useApiPolling";
import { fetchChart } from "../api/pulse";
import type { ChartData } from "../types/pulse";
import type { LaunchOverviewData } from "../types/launch";
import type { NarrativeOverview, NarrativeData, NarrativeTokenData } from "../types/narrative";

// ── Helpers ──

function formatCompact(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
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

// ── Animated Counter ──

function AnimatedNumber({ value, prefix = "", suffix = "" }: { value: number; prefix?: string; suffix?: string }) {
  const [display, setDisplay] = useState(0);
  const prevValue = useRef(0);

  useEffect(() => {
    const start = prevValue.current;
    const end = value;
    const duration = 800;
    const startTime = Date.now();

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setDisplay(Math.round(start + (end - start) * eased));
      if (progress < 1) requestAnimationFrame(animate);
    };

    requestAnimationFrame(animate);
    prevValue.current = value;
  }, [value]);

  return <>{prefix}{display.toLocaleString()}{suffix}</>;
}

// ── Health Gauge ──

function HealthGauge({ score }: { score: number }) {
  const radius = 52;
  const stroke = 6;
  const circumference = Math.PI * radius; // semi-circle
  const fillPct = score / 100;
  const offset = circumference * (1 - fillPct);

  const color = score >= 70 ? "#00e676" : score <= 30 ? "#ff1744" : "#f0b90b";
  const label = score >= 70 ? "Launch Window" : score <= 30 ? "Danger Zone" : "Neutral";

  return (
    <div className="flex flex-col items-center">
      <svg width="120" height="68" viewBox="0 0 120 68">
        {/* Background arc */}
        <path
          d="M 8 64 A 52 52 0 0 1 112 64"
          fill="none" stroke="#1e1e2e" strokeWidth={stroke} strokeLinecap="round"
        />
        {/* Filled arc */}
        <motion.path
          d="M 8 64 A 52 52 0 0 1 112 64"
          fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          style={{ filter: `drop-shadow(0 0 8px ${color}40)` }}
        />
      </svg>
      <div className="text-center -mt-8">
        <div className="text-3xl font-bold" style={{ color }}>{score.toFixed(0)}</div>
        <div className="text-[10px] text-terminal-muted uppercase tracking-wider">{label}</div>
      </div>
    </div>
  );
}

// ── Info Tooltip ──

function InfoTip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block ml-1.5">
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        className="text-terminal-muted/30 hover:text-terminal-muted/60 transition-colors text-[10px]"
      >?</button>
      <AnimatePresence>
        {show && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="absolute z-50 bottom-6 left-1/2 -translate-x-1/2 w-48 px-3 py-2 rounded-lg bg-terminal-card border border-terminal-border text-[11px] text-terminal-muted leading-relaxed shadow-xl"
          >
            {text}
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  );
}

// ── Section Header ──

function SectionHeader({ title, info }: { title: string; info: string }) {
  return (
    <div className="flex items-center gap-1 mb-3">
      <span className="text-[10px] text-terminal-muted/50 uppercase tracking-widest font-medium">{title}</span>
      <InfoTip text={info} />
    </div>
  );
}

// ── Live Pulse ──

function LivePulse() {
  return (
    <span className="relative flex h-2 w-2">
      <span className="animate-ping absolute h-full w-full rounded-full bg-terminal-green opacity-75" />
      <span className="relative rounded-full h-2 w-2 bg-terminal-green" />
    </span>
  );
}

// ── Narrative Card ──

const LIFECYCLE_COLORS: Record<string, string> = {
  emerging: "text-blue-400 bg-blue-400/10 border-blue-400/20",
  trending: "text-terminal-green bg-terminal-green/10 border-terminal-green/20",
  saturated: "text-terminal-accent bg-terminal-accent/10 border-terminal-accent/20",
  fading: "text-terminal-red bg-terminal-red/10 border-terminal-red/20",
};

function NarrativeCard({ narrative, onClick, index }: { narrative: NarrativeData; onClick: () => void; index: number }) {
  const lc = LIFECYCLE_COLORS[narrative.lifecycle] || LIFECYCLE_COLORS.fading;
  return (
    <motion.button
      onClick={onClick}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3 }}
      className="bg-white/[0.02] backdrop-blur-sm border border-white/[0.06] rounded-lg p-3 text-left hover:border-terminal-accent/30 hover:bg-white/[0.04] transition-all w-full"
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm font-bold text-terminal-text">{narrative.name}</span>
        <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${lc} capitalize`}>{narrative.lifecycle}</span>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-terminal-muted">
        <span>{narrative.token_count} tokens</span>
        <span>{formatCompact(narrative.total_volume)} vol</span>
        <span className={narrative.avg_gain_pct > 0 ? "text-terminal-green" : "text-terminal-red"}>
          {formatPct(narrative.avg_gain_pct)}
        </span>
      </div>
    </motion.button>
  );
}

// ── Runner Row ──

function RunnerRow({ token, index }: { token: NarrativeTokenData; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05, duration: 0.25 }}
      className="flex items-center gap-2 py-1.5 border-b border-white/[0.04] last:border-0"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-terminal-text truncate">{token.name}</span>
          {!token.is_original && (
            <span className="text-[8px] px-1 py-0.5 rounded bg-terminal-accent/10 text-terminal-accent">fork</span>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-terminal-muted">
          {token.narrative && <span className="text-terminal-accent">{token.narrative}</span>}
          <span>{formatAge(token.created_at)}</span>
        </div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className={`text-xs font-bold tabular-nums ${(token.price_change_pct ?? 0) > 0 ? "text-terminal-green" : "text-terminal-red"}`}>
          {formatPct(token.price_change_pct)}
        </div>
        <div className="text-[10px] text-terminal-muted tabular-nums">
          {token.mcap ? formatCompact(token.mcap) : "--"}
        </div>
      </div>
      <a href={`https://dexscreener.com/solana/${token.address}`} target="_blank" rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()} className="text-[9px] text-terminal-accent/40 hover:text-terminal-accent flex-shrink-0">DS</a>
    </motion.div>
  );
}

// ── Stat Pill ──

function StatPill({ label, value, color = "text-terminal-text" }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="text-terminal-muted/50">{label}</span>
      <span className={`font-bold tabular-nums ${color}`}>{value}</span>
    </div>
  );
}

// ── Main Dashboard ──

export default function UnifiedDashboard() {
  const navigate = useNavigate();
  const chartRef = useRef<CandlestickChartHandle>(null);
  const initialRangeSet = useRef(false);

  const [chartData, setChartData] = useState<ChartData | null>(null);
  const { data: launchData } = useApiPolling<LaunchOverviewData>("/launch/overview?range=30d", 60000);
  const { data: narrativeData } = useApiPolling<NarrativeOverview>("/narrative/overview", 60000);

  useEffect(() => {
    const exc = ["dex_volume", "stablecoin_supply", "vol_regime", "new_wallets", "priority_fees"];
    fetchChart("all", exc).then(setChartData).catch(() => {});
    const interval = setInterval(async () => {
      try {
        const d = await fetchChart("all", exc);
        setChartData((prev) => {
          if (!prev || d.candles.length !== prev.candles.length) return d;
          const ln = d.candles[d.candles.length - 1];
          const lo = prev.candles[prev.candles.length - 1];
          if (ln?.close !== lo?.close) return d;
          return prev;
        });
      } catch {}
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!chartData || initialRangeSet.current) return;
    const t = setTimeout(() => {
      chartRef.current?.getChart()?.timeScale().fitContent();
      initialRangeSet.current = true;
    }, 500);
    return () => clearTimeout(t);
  }, [chartData]);

  const score = chartData?.scores?.length ? chartData.scores[chartData.scores.length - 1].score : null;
  const activity = launchData?.metrics.find((m) => m.name === "Launchpad Activity");
  const launchCount = activity?.current ?? 0;
  const migrationRate = (activity as Record<string, unknown> | undefined)?.migration_rate as number | undefined;
  const survivalMetric = launchData?.metrics.find((m) => m.name === "Survival Rate (24h)");
  const volumeMetric = launchData?.metrics.find((m) => m.name === "Volume");

  return (
    <div className="max-w-[1400px] mx-auto relative">
      {/* Gradient mesh background */}
      <div className="fixed inset-0 pointer-events-none -z-10">
        <div className="absolute top-0 left-0 w-[600px] h-[600px] bg-purple-900/[0.07] rounded-full blur-[120px]" />
        <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-cyan-900/[0.05] rounded-full blur-[120px]" />
      </div>

      {/* ── Top Bar ── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-4"
      >
        <div className="flex items-center gap-3">
          <span className="text-terminal-accent font-bold text-lg tracking-[0.2em]">CANDLE</span>
          <LivePulse />
        </div>
        <div className="flex items-center gap-4">
          <StatPill label="Launches" value={formatCompact(launchCount)} />
          {migrationRate != null && <StatPill label="Grad" value={`${migrationRate.toFixed(1)}%`} />}
          {survivalMetric?.current != null && <StatPill label="Survival" value={`${survivalMetric.current.toFixed(0)}%`} />}
          {volumeMetric?.current != null && <StatPill label="Vol" value={formatCompact(volumeMetric.current)} />}
        </div>
      </motion.div>

      {/* ── Row 1: Gauge + Chart ── */}
      <div className="grid grid-cols-[140px_1fr] gap-4 mb-4">
        {/* Health Gauge */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1, duration: 0.5 }}
          className="bg-white/[0.02] backdrop-blur-sm border border-white/[0.06] rounded-xl p-3 flex flex-col items-center justify-center"
        >
          {score !== null ? (
            <HealthGauge score={score} />
          ) : (
            <div className="text-terminal-muted text-xs">Loading...</div>
          )}
          <InfoTip text="Market health score based on TVL, Fear & Greed Index, and Chain Fee Revenue. Higher = better conditions for launching." />
        </motion.div>

        {/* Chart */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="bg-white/[0.02] backdrop-blur-sm border border-white/[0.06] rounded-xl overflow-hidden"
        >
          {chartData && chartData.candles.length > 0 ? (
            <CandlestickChart ref={chartRef} candles={chartData.candles} scores={chartData.scores} height={180} />
          ) : (
            <div className="h-[180px] flex items-center justify-center text-terminal-muted text-xs">Loading chart...</div>
          )}
        </motion.div>
      </div>

      {/* ── Row 2: Launch Performance + Launchpad Activity ── */}
      <div className="mb-4">
        <SectionHeader title="Launch Conditions" info="Current market conditions for token launches. Performance tiers show peak mcap distribution. Activity shows launches per platform." />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {launchData?.metrics.filter(m => m.name === "Launch Performance" || m.name === "Launchpad Activity").map((metric) =>
            metric.name === "Launch Performance" ? (
              <LaunchPerformanceCard key={metric.name} metric={metric} />
            ) : (
              <LaunchMigrationCard key={metric.name} metric={metric} />
            )
          )}
        </div>
      </div>

      {/* ── Row 3: Small metric cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        {launchData?.metrics.filter(m => !["Launch Performance", "Launchpad Activity"].includes(m.name)).map((metric, i) => (
          <motion.div
            key={metric.name}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 + i * 0.06 }}
          >
            <LaunchMetricCard metric={metric} />
          </motion.div>
        ))}
      </div>

      {/* ── Row 4: Narratives + Runners ── */}
      <div>
        <SectionHeader title="Trending Narratives" info="AI-classified token themes from DexScreener trending data. Shows what categories are hot right now. Click a narrative to see all tokens in it." />

        <div className="bg-terminal-red/[0.03] border border-terminal-red/10 rounded-lg px-3 py-2 mb-3">
          <p className="text-[10px] text-terminal-red/60">
            Includes unverified tokens for narrative identification. Not investment advice.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
          {/* Narrative cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2.5">
            {narrativeData?.narratives.map((n, i) => (
              <NarrativeCard key={n.name} narrative={n} index={i}
                onClick={() => navigate(`/narrative/${encodeURIComponent(n.name)}`)} />
            ))}
            {(!narrativeData || narrativeData.narratives.length === 0) && (
              <div className="col-span-full text-terminal-muted text-center py-8 text-sm">
                Scanning narratives...
              </div>
            )}
          </div>

          {/* Top Runners */}
          <div>
            <div className="flex items-center gap-1 mb-2">
              <span className="text-[10px] text-terminal-muted/50 uppercase tracking-widest font-medium">Top Runners</span>
              <InfoTip text="Top 10 tokens by percentage gain in the last 24 hours. DS links to DexScreener for charts and trading." />
            </div>
            <div className="bg-white/[0.02] backdrop-blur-sm border border-white/[0.06] rounded-xl p-3">
              {narrativeData?.top_runners.map((t, i) => (
                <RunnerRow key={t.address} token={t} index={i} />
              ))}
              {(!narrativeData || narrativeData.top_runners.length === 0) && (
                <div className="text-terminal-muted text-center py-6 text-xs">No runners yet</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
