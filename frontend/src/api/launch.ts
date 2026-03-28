import { apiFetch } from "./client";
import type { LaunchOverviewData, LaunchMetricData, LaunchRange } from "../types/launch";

export function fetchLaunchOverview(range: LaunchRange = "30d"): Promise<LaunchOverviewData> {
  return apiFetch<LaunchOverviewData>(`/launch/overview?range=${range}`);
}

export function fetchLaunchMetric(
  slug: string,
  range: LaunchRange = "30d"
): Promise<LaunchMetricData> {
  return apiFetch<LaunchMetricData>(`/launch/${slug}?range=${range}`);
}
