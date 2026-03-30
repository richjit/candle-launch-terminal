import PageLayout from "../components/layout/PageLayout";
import LaunchMetricCard from "../components/launch/LaunchMetricCard";
import LaunchPerformanceCard from "../components/launch/LaunchPerformanceCard";
import LaunchMigrationCard from "../components/launch/LaunchMigrationCard";
import { useApiPolling } from "../hooks/useApiPolling";
import type { LaunchOverviewData } from "../types/launch";

function formatCompact(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

function HeroSummary({ data }: { data: LaunchOverviewData }) {
  const metrics = data.metrics;
  const activity = metrics.find((m) => m.name === "Launchpad Activity");
  const migration = activity; // Same metric now
  const survival = metrics.find((m) => m.name === "Survival Rate (24h)");
  const volume = metrics.find((m) => m.name === "Volume");

  const launchCount = activity?.current ?? 0;
  const migrationRate = (activity as Record<string, unknown> | undefined)?.migration_rate as number | undefined;
  const survivalRate = survival?.current;

  // Determine overall market condition
  let condition: "hot" | "warm" | "cold" = "warm";
  if (survivalRate !== null && survivalRate !== undefined) {
    if (survivalRate > 50 && launchCount > 300) condition = "hot";
    else if (survivalRate < 30 || launchCount < 100) condition = "cold";
  }

  const conditionLabel = { hot: "Active", warm: "Normal", cold: "Quiet" };
  const conditionColor = {
    hot: "text-terminal-green",
    warm: "text-terminal-accent",
    cold: "text-terminal-muted",
  };
  const conditionDot = {
    hot: "bg-terminal-green shadow-[0_0_8px_rgba(0,230,118,0.5)]",
    warm: "bg-terminal-accent shadow-[0_0_8px_rgba(240,185,11,0.5)]",
    cold: "bg-terminal-muted",
  };

  return (
    <div className="bg-terminal-card border border-terminal-border rounded-lg p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        {/* Left: headline stats */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className={`w-2.5 h-2.5 rounded-full ${conditionDot[condition]}`} />
            <span className={`text-sm font-semibold uppercase tracking-wider ${conditionColor[condition]}`}>
              Market {conditionLabel[condition]}
            </span>
          </div>
          <div className="text-3xl font-bold text-terminal-text">
            {launchCount.toLocaleString()} <span className="text-lg font-normal text-terminal-muted">launches (24h)</span>
          </div>
          {migrationRate !== null && migrationRate !== undefined && (
            <div className="text-sm text-terminal-muted mt-1">
              {migrationRate.toFixed(1)}% graduation rate
            </div>
          )}
        </div>

        {/* Right: quick stats */}
        <div className="flex gap-6">
          {survivalRate !== null && survivalRate !== undefined && (
            <div className="text-right">
              <div className="text-xs text-terminal-muted uppercase tracking-wider">Survival</div>
              <div className={`text-xl font-bold ${survivalRate > 50 ? "text-terminal-green" : survivalRate < 30 ? "text-terminal-red" : "text-terminal-text"}`}>
                {survivalRate.toFixed(0)}%
              </div>
            </div>
          )}
          {volume?.current !== null && volume?.current !== undefined && (
            <div className="text-right">
              <div className="text-xs text-terminal-muted uppercase tracking-wider">DEX Volume</div>
              <div className="text-xl font-bold text-terminal-text">
                {formatCompact(volume.current)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LaunchDashboard() {
  const { data, loading, error } = useApiPolling<LaunchOverviewData>(
    `/launch/overview?range=30d`,
    60000,
  );

  return (
    <PageLayout title="Launch Monitor">
      <div className="mb-4">
        <p className="text-sm text-terminal-muted">
          Real-time Solana token launch intelligence
        </p>
      </div>

      {loading && !data && (
        <div className="text-terminal-muted text-center py-16">
          Loading launch data...
        </div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}

      {data && (
        <>
          <HeroSummary data={data} />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {data.metrics.map((metric) =>
              metric.name === "Launch Performance" ? (
                <LaunchPerformanceCard key={metric.name} metric={metric} />
              ) : metric.name === "Launchpad Activity" ? (
                <LaunchMigrationCard key={metric.name} metric={metric} />
              ) : (
                <LaunchMetricCard key={metric.name} metric={metric} />
              )
            )}
          </div>

          <div className="text-[11px] text-terminal-muted/40 text-right mt-4">
            Updated {new Date(data.last_updated).toLocaleTimeString()}
          </div>
        </>
      )}
    </PageLayout>
  );
}
