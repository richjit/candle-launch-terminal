// frontend/src/pages/Pulse.tsx
import PageLayout from "../components/layout/PageLayout";
import ScoreCard from "../components/scores/ScoreCard";
import FactorBreakdown from "../components/scores/FactorBreakdown";
import MetricCard from "../components/charts/MetricCard";
import LastUpdated from "../components/common/LastUpdated";
import TimeSeriesChart from "../components/charts/TimeSeriesChart";
import { useApiPolling } from "../hooks/useApiPolling";
import { PulseData } from "../types/api";

function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(2);
}

export default function Pulse() {
  const { data, loading, lastUpdated } = useApiPolling<PulseData>("/pulse", 30000);

  return (
    <PageLayout title="Solana Market Pulse">
      <div className="flex justify-end mb-4">
        <LastUpdated timestamp={lastUpdated?.toISOString() ?? null} />
      </div>

      {/* Health Score */}
      <div className="mb-4">
        <ScoreCard title="Solana Health Score" score={data?.health_score ?? null} />
      </div>
      <div className="mb-6">
        <FactorBreakdown factors={data?.health_score?.factors ?? []} />
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard
          label="SOL Price"
          value={data?.sol_price ? `$${data.sol_price.value.toFixed(2)}` : null}
          changePercent={data?.sol_price?.change_24h}
          subValue="24h"
        />
        <MetricCard
          label="Network TPS"
          value={data?.tps?.current ? Math.round(data.tps.current).toLocaleString() : null}
          subValue="tx/sec"
        />
        <MetricCard
          label="Priority Fees"
          value={data?.priority_fees?.current ? Math.round(data.priority_fees.current).toLocaleString() : null}
          subValue="avg microlamports"
        />
        <MetricCard
          label="Fear & Greed"
          value={data?.fear_greed?.value ?? null}
          subValue={data?.fear_greed?.label}
        />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard
          label="DEX Volume (24h)"
          value={data?.dex_volume ? formatNumber(data.dex_volume.current) : null}
          subValue="Solana"
        />
        <MetricCard
          label="Total Value Locked"
          value={data?.tvl ? formatNumber(data.tvl.current) : null}
          subValue="Solana"
        />
        <MetricCard
          label="Stablecoin Supply"
          value={data?.stablecoin_supply ? formatNumber(data.stablecoin_supply.total) : null}
          subValue={data?.stablecoin_supply ? `USDC: ${formatNumber(data.stablecoin_supply.usdc)}` : undefined}
        />
        <MetricCard
          label="Google Trends"
          value={data?.google_trends?.solana ?? null}
          subValue={data?.google_trends ? `ETH: ${data.google_trends.ethereum} | BTC: ${data.google_trends.bitcoin}` : undefined}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TimeSeriesChart
          data={data?.tvl?.history ?? []}
          label="Solana TVL (30d)"
          color="#f0b90b"
          height={250}
          formatValue={(v) => `$${(v / 1e9).toFixed(2)}B`}
        />
      </div>

      {loading && !data && (
        <div className="text-terminal-muted text-center py-8">Loading pulse data...</div>
      )}
    </PageLayout>
  );
}
