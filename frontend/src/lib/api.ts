import type { Candle, Pattern, PatternStatus, SystemConfig } from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getConfig: () => request<SystemConfig>("/api/config"),
  updateConfig: (payload: Omit<SystemConfig, "id">) =>
    request<SystemConfig>("/api/config", { method: "PUT", body: JSON.stringify(payload) }),
  getPatterns: (status?: PatternStatus) =>
    request<Pattern[]>(`/api/patterns${status ? `?status=${status}` : ""}`),
  getCandles: (symbol: string, timeframe = "15m") =>
    request<Candle[]>(`/api/candles/${symbol}?timeframe=${timeframe}`),
  panic: () => request<{ status: string }>("/api/panic", { method: "POST" })
};
