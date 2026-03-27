export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface ScorePoint {
  time: number;
  score: number;
}

export interface ChartData {
  candles: Candle[];
  scores: ScorePoint[];
  range: string;
}

export interface CorrelationFactor {
  name: string;
  label: string;
  correlation: number;
  optimal_lag_days: number;
  weight: number;
  in_score: boolean;
}

export interface CorrelationsData {
  factors: CorrelationFactor[];
  last_computed: string | null;
}

export interface EcosystemMetric {
  name: string;
  label: string;
  current: number;
  sparkline: number[];
  direction: "up" | "down" | null;
  sub_values?: Record<string, number>;
}

export interface EcosystemData {
  metrics: EcosystemMetric[];
  last_updated: string;
}

export type ChartRange = "30d" | "90d" | "1y" | "all";
