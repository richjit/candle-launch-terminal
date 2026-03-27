export interface MetricValue {
  metric_name: string;
  value: number;
  metadata: Record<string, unknown> | null;
  fetched_at: string;
}

export interface SourceStatus {
  source: string;
  last_fetch_at: string | null;
  error_count: number;
  circuit_open: boolean;
}

export interface HealthResponse {
  status: string;
  sources: SourceStatus[];
}

