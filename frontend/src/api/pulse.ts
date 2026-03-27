import { apiFetch } from "./client";
import type { ChartData, CorrelationsData, EcosystemData, ChartRange } from "../types/pulse";

export function fetchChart(range: ChartRange = "30d"): Promise<ChartData> {
  return apiFetch<ChartData>(`/pulse/chart?range=${range}`);
}

export function fetchCorrelations(): Promise<CorrelationsData> {
  return apiFetch<CorrelationsData>("/pulse/correlations");
}

export function fetchEcosystem(): Promise<EcosystemData> {
  return apiFetch<EcosystemData>("/pulse/ecosystem");
}
