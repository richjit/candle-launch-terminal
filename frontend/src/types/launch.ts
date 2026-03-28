export interface LaunchChartPoint {
  date: string;
  value: number | null;
}

export interface LaunchMetricData {
  name: string;
  current: number | null;
  trend: "up" | "down" | "flat";
  last_updated: string;
  chart: LaunchChartPoint[];
  breakdown?: Record<string, number | null>;
}

export interface LaunchOverviewData {
  metrics: LaunchMetricData[];
  last_updated: string;
}

export type LaunchRange = "7d" | "30d" | "90d";

// Metric slugs used in URLs
export type LaunchMetricSlug =
  | "migration-rate"
  | "peak-mcap"
  | "time-to-peak"
  | "survival"
  | "buy-sell"
  | "launches"
  | "volume"
  | "capital-flow";
