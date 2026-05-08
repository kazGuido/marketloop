import { useEffect, useState } from "react";

import { HarmonicChart } from "./components/HarmonicChart";
import { Header } from "./components/Header";
import { SignalSidebar } from "./components/SignalSidebar";
import { api } from "./lib/api";
import type { Pattern, StrategyConfig, StrategyPerformance, SystemConfig } from "./types/api";

export default function App() {
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [strategy, setStrategy] = useState<StrategyConfig | null>(null);
  const [strategies, setStrategies] = useState<StrategyConfig[]>([]);
  const [performance, setPerformance] = useState<StrategyPerformance[]>([]);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [selectedPattern, setSelectedPattern] = useState<Pattern | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getConfig().then(setConfig).catch((err) => setError(err.message));
    api.getStrategy().then(setStrategy).catch((err) => setError(err.message));
    api.getStrategies().then(setStrategies).catch((err) => setError(err.message));
    api.getStrategyPerformance().then(setPerformance).catch(() => undefined);
  }, []);

  useEffect(() => {
    let active = true;
    async function loadPatterns() {
      try {
        const data = await api.getPatterns("ACTIVE");
        if (!active) return;
        setPatterns(data);
        setSelectedPattern((current) => current ?? data[0] ?? null);
      } catch (err) {
        if (err instanceof Error) setError(err.message);
      }
    }
    loadPatterns();
    const interval = window.setInterval(loadPatterns, 15_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Header
        config={config}
        strategy={strategy}
        strategies={strategies}
        performance={performance}
        onConfigChange={setConfig}
        onStrategyChange={(next) => {
          setStrategy(next);
          api.getStrategies().then(setStrategies).catch(() => undefined);
        }}
        onStrategiesChange={setStrategies}
        onPerformanceChange={setPerformance}
      />
      {error && (
        <div className="border-b border-red-900 bg-red-950/70 px-5 py-3 text-sm text-red-100">
          Backend error: {error}
        </div>
      )}
      <main className="flex min-h-[calc(100vh-88px)] flex-col lg:flex-row">
        <SignalSidebar patterns={patterns} selectedPattern={selectedPattern} onSelect={setSelectedPattern} />
        <HarmonicChart pattern={selectedPattern} />
      </main>
    </div>
  );
}
