export interface LaunchChartPoint {
  date: string;
  value: number | null;
}

export interface LaunchPerformanceTiers {
  bonded: number;
  top10: number;
  top1: number;
  best24h: number;
  sample_size: number;
  all_median?: number;
  all_count?: number;
  best_address?: string;
  best_pair?: string;
  time_to_peak?: {
    bonded: number | null;
    top10: number | null;
    top1: number | null;
    best24h: number | null;
  };
}

export interface LaunchMetricData {
  name: string;
  current: number | null;
  trend: "up" | "down" | "flat";
  last_updated: string;
  chart: LaunchChartPoint[];
  breakdown?: Record<string, number | null>;
  tiers?: LaunchPerformanceTiers;
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
  | "volume";
