// frontend/src/api/pulse.ts
import { apiFetch } from "./client";
import { PulseData } from "../types/api";

export function fetchPulse(): Promise<PulseData> {
  return apiFetch<PulseData>("/pulse");
}
