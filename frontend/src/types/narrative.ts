export interface NarrativeData {
  name: string;
  token_count: number;
  total_volume: number;
  avg_gain_pct: number;
  lifecycle: "emerging" | "trending" | "saturated" | "fading";
  top_token_address: string | null;
  last_updated: string | null;
}

export interface NarrativeTokenData {
  address: string;
  name: string;
  symbol: string;
  narrative: string | null;
  mcap: number | null;
  price_change_pct: number | null;
  volume_24h: number | null;
  liquidity_usd: number | null;
  is_original: boolean;
  parent_address: string | null;
  pair_address: string;
  created_at: string | null;
}

export interface NarrativeOverview {
  narratives: NarrativeData[];
  top_runners: NarrativeTokenData[];
}

export interface NarrativeDetail {
  name: string;
  token_count: number;
  total_volume: number;
  avg_gain_pct: number;
  lifecycle: string;
  tokens: NarrativeTokenData[];
}
