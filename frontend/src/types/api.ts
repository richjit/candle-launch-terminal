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

export interface ScoreFactor {
  name: string;
  value: number;
  normalized: number; // -1 to +1
  contribution: number;
  label: string;
}

export interface CompositeScore {
  score: number;
  max_score: number;
  factors_available: number;
  factors_total: number;
  factors: ScoreFactor[];
}

export interface PulseData {
  health_score: CompositeScore;
  sol_price: { value: number; change_24h: number; change_7d: number; change_30d: number } | null;
  tps: { current: number; history: Array<{ timestamp: string; value: number }> } | null;
  priority_fees: { current: number; history: Array<{ timestamp: string; value: number }> } | null;
  stablecoin_supply: { total: number; usdc: number; usdt: number } | null;
  dex_volume: { current: number; fetched_at?: string } | null;
  tvl: { current: number; history?: Array<{ timestamp: string | number; value: number }>; chains?: Record<string, number> } | null;
  stablecoin_flows: { solana: number; chains: Record<string, number> } | null;
  fear_greed: { value: number; label: string } | null;
  google_trends: { solana: number; ethereum: number; bitcoin: number } | null;
  last_updated: string;
}
