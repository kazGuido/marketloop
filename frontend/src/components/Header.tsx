import { FormEvent, useEffect, useState } from "react";

import { api } from "../lib/api";
import type { OperationMode, StrategyConfig, StrategyPerformance, SystemConfig } from "../types/api";

interface HeaderProps {
  config: SystemConfig | null;
  strategy: StrategyConfig | null;
  strategies: StrategyConfig[];
  performance: StrategyPerformance[];
  onConfigChange: (config: SystemConfig) => void;
  onStrategyChange: (strategy: StrategyConfig) => void;
  onStrategiesChange: (strategies: StrategyConfig[]) => void;
  onPerformanceChange: (performance: StrategyPerformance[]) => void;
}

export function Header({
  config,
  strategy,
  strategies,
  performance,
  onConfigChange,
  onStrategyChange,
  onStrategiesChange,
  onPerformanceChange
}: HeaderProps) {
  const [assetPool, setAssetPool] = useState("BTC,ETH,SOL");
  const [risk, setRisk] = useState(1.5);
  const [strategyName, setStrategyName] = useState("rent-and-utilities");
  const [scoreThreshold, setScoreThreshold] = useState(80);
  const [minRewardRisk, setMinRewardRisk] = useState(1.2);
  const [maxAtrPct, setMaxAtrPct] = useState(3.5);
  const [imbalanceRatio, setImbalanceRatio] = useState(3);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (config) {
      setAssetPool(config.asset_pool.join(","));
      setRisk(config.risk_per_trade);
    }
  }, [config]);

  useEffect(() => {
    if (strategy) {
      setStrategyName(strategy.name);
      setScoreThreshold(strategy.score_threshold);
      setMinRewardRisk(strategy.min_net_reward_risk);
      setMaxAtrPct(strategy.max_atr_pct * 100);
      setImbalanceRatio(strategy.orderbook_imbalance_ratio);
    }
  }, [strategy]);

  async function saveConfig(nextMode?: OperationMode) {
    if (!config) return;
    setSaving(true);
    try {
      const assets = assetPool.trim().toUpperCase() === "ALL" ? ["ALL"] : assetPool.split(",");
      const updated = await api.updateConfig({
        operation_mode: nextMode ?? config.operation_mode,
        asset_pool: assets,
        risk_per_trade: risk
      });
      onConfigChange(updated);
    } finally {
      setSaving(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    await Promise.all([saveConfig(), saveStrategy()]);
  }

  async function saveStrategy() {
    if (!strategy) return;
    const updated = await api.updateStrategy({
      ...strategy,
      name: strategyName,
      score_threshold: scoreThreshold,
      min_net_reward_risk: minRewardRisk,
      max_atr_pct: maxAtrPct / 100,
      orderbook_imbalance_ratio: imbalanceRatio
    });
    onStrategyChange(updated);
  }

  async function refreshStrategies() {
    const [nextStrategies, nextPerformance] = await Promise.all([
      api.getStrategies(),
      api.getStrategyPerformance().catch(() => [] as StrategyPerformance[])
    ]);
    onStrategiesChange(nextStrategies);
    onPerformanceChange(nextPerformance);
  }

  async function activateStrategy(id: number) {
    const updated = await api.activateStrategy(id);
    onStrategyChange(updated);
    await refreshStrategies();
  }

  async function saveAsNewStrategy() {
    if (!strategy) return;
    const created = await api.createStrategy({
      ...strategy,
      name: `${strategyName} copy`,
      active: false,
      score_threshold: scoreThreshold,
      min_net_reward_risk: minRewardRisk,
      max_atr_pct: maxAtrPct / 100,
      orderbook_imbalance_ratio: imbalanceRatio
    });
    onStrategyChange(created);
    await refreshStrategies();
  }

  async function replayActiveStrategy() {
    if (!strategy) return;
    const result = await api.replayStrategy(strategy.id);
    onPerformanceChange([result, ...performance.filter((item) => item.strategy_config_id !== strategy.id)]);
  }

  async function panic() {
    if (!window.confirm("Close all tracked/open Hyperliquid positions now?")) return;
    await api.panic();
  }

  const mode = config?.operation_mode ?? "SIGNAL_ONLY";

  return (
    <header className="border-b border-slate-800 bg-slate-950/90 px-5 py-4 backdrop-blur">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-300">Harmonic Sentinel</p>
          <h1 className="text-2xl font-semibold text-white">Deterministic Hyperliquid Scanner</h1>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="rounded-full border border-slate-700 bg-slate-900 p-1">
            {(["SIGNAL_ONLY", "AUTO_TRADE"] as OperationMode[]).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => saveConfig(item)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  mode === item ? "bg-cyan-400 text-slate-950" : "text-slate-300 hover:text-white"
                }`}
              >
                {item === "SIGNAL_ONLY" ? "Signal Mode" : "Auto-Trade Mode"}
              </button>
            ))}
          </div>

          <label className="text-sm text-slate-300">
            Strategy
            <select
              value={strategy?.id ?? ""}
              onChange={(event) => activateStrategy(Number(event.target.value))}
              className="mt-1 block w-48 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
            >
              {strategies.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.active ? "* " : ""}
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <label className="text-sm text-slate-300">
            Strategy Name
            <input
              value={strategyName}
              onChange={(event) => setStrategyName(event.target.value)}
              className="mt-1 block w-44 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
            />
          </label>

          <label className="text-sm text-slate-300">
            Asset Pool
            <input
              value={assetPool}
              onChange={(event) => setAssetPool(event.target.value)}
              className="mt-1 block w-48 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
              placeholder="BTC,ETH,SOL or ALL"
            />
          </label>

          <label className="text-sm text-slate-300">
            Risk %
            <input
              type="number"
              min="0.01"
              max="25"
              step="0.1"
              value={risk}
              onChange={(event) => setRisk(Number(event.target.value))}
              className="mt-1 block w-24 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
            />
          </label>

          <label className="text-sm text-slate-300">
            Score
            <input
              type="number"
              min="1"
              max="100"
              value={scoreThreshold}
              onChange={(event) => setScoreThreshold(Number(event.target.value))}
              className="mt-1 block w-20 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
            />
          </label>

          <label className="text-sm text-slate-300">
            Min R:R
            <input
              type="number"
              min="0.1"
              max="10"
              step="0.1"
              value={minRewardRisk}
              onChange={(event) => setMinRewardRisk(Number(event.target.value))}
              className="mt-1 block w-24 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
            />
          </label>

          <label className="text-sm text-slate-300">
            Max ATR %
            <input
              type="number"
              min="0.1"
              max="20"
              step="0.1"
              value={maxAtrPct}
              onChange={(event) => setMaxAtrPct(Number(event.target.value))}
              className="mt-1 block w-24 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
            />
          </label>

          <label className="text-sm text-slate-300">
            L2 x
            <input
              type="number"
              min="1"
              max="20"
              step="0.1"
              value={imbalanceRatio}
              onChange={(event) => setImbalanceRatio(Number(event.target.value))}
              className="mt-1 block w-20 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
            />
          </label>

          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-slate-100 px-4 py-2 font-semibold text-slate-950 hover:bg-white disabled:opacity-60"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          <button
            type="button"
            onClick={saveAsNewStrategy}
            className="rounded-lg bg-slate-800 px-4 py-2 font-semibold text-slate-100 hover:bg-slate-700"
          >
            Save Strategy
          </button>
          <button
            type="button"
            onClick={replayActiveStrategy}
            className="rounded-lg bg-cyan-500 px-4 py-2 font-semibold text-slate-950 hover:bg-cyan-400"
          >
            Replay
          </button>
          <button
            type="button"
            onClick={panic}
            className="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white shadow-lg shadow-red-950/40 hover:bg-red-500"
          >
            Kill Switch
          </button>
        </form>
      </div>
      {strategy && (
        <div className="mt-3 text-xs text-slate-400">
          {performance.find((item) => item.strategy_config_id === strategy.id) ? (
            <span>
              Latest replay: PF{" "}
              {performance.find((item) => item.strategy_config_id === strategy.id)?.profit_factor.toFixed(2)} | win{" "}
              {((performance.find((item) => item.strategy_config_id === strategy.id)?.win_rate ?? 0) * 100).toFixed(1)}%
              {performance.find((item) => item.strategy_config_id === strategy.id)?.degraded ? (
                <span className="ml-2 text-red-300">degraded</span>
              ) : (
                <span className="ml-2 text-emerald-300">healthy/insufficient sample</span>
              )}
            </span>
          ) : (
            <span>No replay snapshot yet for this strategy.</span>
          )}
        </div>
      )}
    </header>
  );
}
