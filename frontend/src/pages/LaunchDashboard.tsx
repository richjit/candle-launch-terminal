import PageLayout from "../components/layout/PageLayout";
import LaunchMetricCard from "../components/launch/LaunchMetricCard";
import { useApiPolling } from "../hooks/useApiPolling";
import type { LaunchOverviewData } from "../types/launch";

export default function LaunchDashboard() {
  const { data, loading, error } = useApiPolling<LaunchOverviewData>(
    "/launch/overview?range=30d",
    60000,
  );

  return (
    <PageLayout title="Launch Monitor">
      {loading && !data && (
        <div className="text-terminal-muted text-center py-16">
          Loading launch data...
        </div>
      )}

      {error && (
        <div className="text-terminal-red text-center py-4 text-sm">{error}</div>
      )}

      {data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {data.metrics.map((metric) => (
            <LaunchMetricCard key={metric.name} metric={metric} />
          ))}
        </div>
      )}

      {data && data.metrics.every((m) => m.current === null) && (
        <div className="text-terminal-muted text-center py-8 text-sm">
          Data collection has started. Metrics will appear as data accumulates.
        </div>
      )}
    </PageLayout>
  );
}
