import { apiFetch } from "./client";
import type { ChartData, CorrelationsData, EcosystemData, ChartRange } from "../types/pulse";

export function fetchChart(range: ChartRange = "30d", exclude?: string[]): Promise<ChartData> {
  let url = `/pulse/chart?range=${range}`;
  if (exclude && exclude.length > 0) {
    url += `&exclude=${exclude.join(",")}`;
  }
  return apiFetch<ChartData>(url);
}

export function fetchCorrelations(): Promise<CorrelationsData> {
  return apiFetch<CorrelationsData>("/pulse/correlations");
}

export function fetchEcosystem(): Promise<EcosystemData> {
  return apiFetch<EcosystemData>("/pulse/ecosystem");
}
