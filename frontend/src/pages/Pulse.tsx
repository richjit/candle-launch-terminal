import { useState, useEffect, useCallback, useRef } from "react";
import type { IChartApi } from "lightweight-charts";
import PageLayout from "../components/layout/PageLayout";
import CandlestickChart, { type CandlestickChartHandle } from "../components/charts/CandlestickChart";
import ScoreLine, { type ScoreLineHandle } from "../components/charts/ScoreLine";
import RangeSelector from "../components/charts/RangeSelector";
import EcosystemCard from "../components/charts/EcosystemCard";
import ScoredFactors from "../components/charts/ScoredFactors";
import { fetchChart, fetchCorrelations, fetchEcosystem } from "../api/pulse";
import type { ChartData, CorrelationsData, EcosystemData, ChartRange } from "../types/pulse";

export default function Pulse() {
  const [range, setRange] = useState<ChartRange>("30d");
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [correlations, setCorrelations] = useState<CorrelationsData | null>(null);
  const [ecosystem, setEcosystem] = useState<EcosystemData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Chart refs for bidirectional crosshair sync
  const candleChartRef = useRef<CandlestickChartHandle>(null);
  const scoreLineRef = useRef<ScoreLineHandle>(null);
  const [candleChart, setCandleChart] = useState<IChartApi | null>(null);
  const [scoreChart, setScoreChart] = useState<IChartApi | null>(null);

  // Load chart data when range changes
  const loadChart = useCallback(async (r: ChartRange) => {
    try {
      const data = await fetchChart(r);
      setChartData(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load chart");
    }
  }, []);

  // Initial load: chart + correlations + ecosystem in parallel
  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const [chart, corr, eco] = await Promise.all([
          fetchChart(range),
          fetchCorrelations(),
          fetchEcosystem(),
        ]);
        setChartData(chart);
        setCorrelations(corr);
        setEcosystem(eco);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Get chart refs after mount for bidirectional crosshair sync
  useEffect(() => {
    if (candleChartRef.current) {
      setCandleChart(candleChartRef.current.getChart());
    }
    if (scoreLineRef.current) {
      setScoreChart(scoreLineRef.current.getChart());
    }
  }, [chartData]);

  // Poll ecosystem every 30s
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const eco = await fetchEcosystem();
        setEcosystem(eco);
      } catch {
        // Silently ignore poll failures
      }
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // Range change handler
  const handleRangeChange = useCallback(
    (r: ChartRange) => {
      setRange(r);
      loadChart(r);
    },
    [loadChart]
  );

  // Current score from latest data point
  const currentScore = chartData?.scores?.length
    ? chartData.scores[chartData.scores.length - 1].score
    : null;

  return (
    <PageLayout title="Solana Market Pulse">
      {/* Header with score and range selector */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          {currentScore !== null && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-terminal-muted uppercase">Health</span>
              <span
                className={`text-2xl font-bold ${
                  currentScore >= 70
                    ? "text-terminal-green"
                    : currentScore <= 30
                      ? "text-terminal-red"
                      : "text-terminal-accent"
                }`}
              >
                {currentScore.toFixed(0)}
              </span>
            </div>
          )}
        </div>
        <RangeSelector selected={range} onChange={handleRangeChange} />
      </div>

      {/* Candlestick Chart + Score Line (synced crosshair) */}
      {chartData && chartData.candles.length > 0 && (
        <>
          <CandlestickChart
            ref={candleChartRef}
            candles={chartData.candles}
            scores={chartData.scores}
            height={400}
            syncedChart={scoreChart}
          />
          <ScoreLine
            ref={scoreLineRef}
            scores={chartData.scores}
            height={150}
            syncedChart={candleChart}
          />
        </>
      )}

      {loading && !chartData && (
        <div className="text-terminal-muted text-center py-16">Loading chart data...</div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}

      {/* Scored Factors */}
      {correlations && (
        <div className="mt-6">
          <ScoredFactors factors={correlations.factors} />
        </div>
      )}

      {/* Ecosystem Cards */}
      {ecosystem && ecosystem.metrics.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs text-terminal-muted uppercase tracking-wider mb-3">
            Ecosystem Snapshot
          </h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {ecosystem.metrics.map((m) => (
              <EcosystemCard key={m.name} metric={m} />
            ))}
          </div>
        </div>
      )}
    </PageLayout>
  );
}
