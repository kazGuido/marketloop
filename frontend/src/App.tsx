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

  const activePerformance = strategy
    ? performance.find((item) => item.strategy_config_id === strategy.id)
    : undefined;

  return (
    <div className="flex h-screen overflow-hidden bg-background text-on-surface">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-outline-variant bg-surface-container-low xl:flex">
        <div className="px-md pb-lg pt-md">
          <div className="label-caps opacity-70">Strategy Hub</div>
          <div className="mt-sm flex items-center gap-sm">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-primary-container/40 bg-primary-container/10 text-primary-fixed-dim shadow-terminal-glow">
              <span className="font-data-mono text-[13px]">DH</span>
            </div>
            <div>
              <div className="font-h2 text-h2 leading-none">Sentinel Core</div>
              <div className="font-body-sm text-body-sm text-on-surface-variant opacity-60">v4.0.1 Harmonic</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-gutter px-xs">
          {[
            ["Terminal", "grid"],
            ["Signals", "pulse"],
            ["Portfolio", "wallet"],
            ["History", "ledger"]
          ].map(([label, glyph], index) => (
            <div
              key={label}
              className={`flex items-center gap-md px-md py-sm transition ${
                index === 0
                  ? "border-r-2 border-primary-fixed-dim bg-primary-container/10 text-primary-fixed-dim"
                  : "text-on-surface-variant opacity-60 hover:bg-surface-container-high hover:opacity-100"
              }`}
            >
              <span className="font-data-mono text-[11px] uppercase">{glyph}</span>
              <span className="font-label-caps text-label-caps">{label}</span>
            </div>
          ))}
        </nav>

        <div className="space-y-md border-t border-outline-variant p-md">
          <button className="w-full bg-primary-container px-md py-sm font-label-caps text-label-caps text-on-primary-container transition hover:brightness-110">
            Deploy Pattern
          </button>
          <div className="space-y-gutter">
            <div className="flex items-center gap-md px-md py-sm text-on-surface-variant opacity-60">
              <span className="font-data-mono text-[11px]">wifi</span>
              <span className="font-label-caps text-label-caps">Connection</span>
            </div>
            <div className="flex items-center gap-md px-md py-sm text-on-surface-variant opacity-60">
              <span className="font-data-mono text-[11px]">docs</span>
              <span className="font-label-caps text-label-caps">Docs</span>
            </div>
          </div>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
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
          <div className="border-b border-secondary-container bg-secondary-container/20 px-md py-sm font-body-sm text-body-sm text-secondary">
            Backend error: {error}
          </div>
        )}

        <div className="flex min-h-0 flex-1 flex-col-reverse overflow-hidden lg:flex-row">
          <HarmonicChart pattern={selectedPattern} />
          <SignalSidebar patterns={patterns} selectedPattern={selectedPattern} onSelect={setSelectedPattern} />
        </div>

        <footer className="flex h-16 shrink-0 items-center justify-between gap-lg border-t border-outline-variant bg-surface-container-low px-lg">
          <div className="flex min-w-0 items-center gap-xl">
            <div>
              <div className="label-caps opacity-50">24H Performance</div>
              <div className="mt-xs flex items-center gap-md">
                <span className="font-data-mono text-h2 text-primary-container">
                  {activePerformance ? `${activePerformance.expectancy_r >= 0 ? "+" : ""}${activePerformance.expectancy_r.toFixed(2)}R` : "+0.00R"}
                </span>
                <span className="h-6 w-gutter bg-outline-variant" />
                <Metric label="Win Rate" value={activePerformance ? `${(activePerformance.win_rate * 100).toFixed(1)}%` : "--"} />
                <Metric label="P-Factor" value={activePerformance ? activePerformance.profit_factor.toFixed(2) : "--"} />
                <Metric
                  label="Max DD"
                  value={activePerformance ? `${activePerformance.max_drawdown_r.toFixed(1)}R` : "--"}
                  tone="danger"
                />
              </div>
            </div>
            <div className="hidden h-8 w-64 overflow-hidden border border-outline-variant bg-surface md:block">
              <div className="h-full bg-primary-container/20" style={{ width: `${Math.min(patterns.length * 12, 82)}%` }} />
              <div className="-mt-8 flex h-8 items-center px-md font-data-mono text-[10px]">
                STRATEGY CAPACITY: {Math.min(patterns.length * 12, 82).toFixed(1)}%
              </div>
            </div>
          </div>
          <div className="hidden items-center gap-md font-data-mono text-[10px] text-on-surface-variant md:flex">
            <span className="flex items-center gap-xs">
              <span className="h-2 w-2 rounded-full bg-primary-container" />
              CORE NODE: ONLINE
            </span>
            <span className="flex items-center gap-xs">
              <span className="h-2 w-2 rounded-full bg-primary-container" />
              ACTIVE PATTERNS: {patterns.length}
            </span>
          </div>
        </footer>
      </main>
    </div>
  );
}

function Metric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "danger" }) {
  return (
    <div className="flex flex-col">
      <span className="font-label-caps text-[10px] uppercase text-on-surface-variant opacity-60">{label}</span>
      <span className={`font-data-mono text-data-mono ${tone === "danger" ? "text-secondary" : "text-on-surface"}`}>
        {value}
      </span>
    </div>
  );
}
