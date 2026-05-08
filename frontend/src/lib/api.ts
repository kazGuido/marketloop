import type { Candle, Pattern, PatternStatus, StrategyConfig, StrategyPerformance, SystemConfig } from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { "x-api-key": API_KEY } : {}),
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
  getStrategy: () => request<StrategyConfig>("/api/strategy"),
  updateStrategy: (payload: Omit<StrategyConfig, "id">) =>
    request<StrategyConfig>("/api/strategy", { method: "PUT", body: JSON.stringify(payload) }),
  getStrategies: () => request<StrategyConfig[]>("/api/strategies"),
  createStrategy: (payload: Omit<StrategyConfig, "id">) =>
    request<StrategyConfig>("/api/strategies", { method: "POST", body: JSON.stringify(payload) }),
  activateStrategy: (id: number) => request<StrategyConfig>(`/api/strategies/${id}/activate`, { method: "POST" }),
  replayStrategy: (id: number) => request<StrategyPerformance>(`/api/strategies/${id}/replay`, { method: "POST" }),
  getStrategyPerformance: () => request<StrategyPerformance[]>("/api/strategy-performance"),
  getPatterns: (status?: PatternStatus) =>
    request<Pattern[]>(`/api/patterns${status ? `?status=${status}` : ""}`),
  getCandles: (symbol: string, timeframe = "15m") =>
    request<Candle[]>(`/api/candles/${symbol}?timeframe=${timeframe}`),
  panic: () => request<{ status: string }>("/api/panic", { method: "POST" })
};
