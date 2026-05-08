import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";

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
  const [telegramEnabled, setTelegramEnabled] = useState(true);
  const [telegramChatId, setTelegramChatId] = useState("");
  const [whatsappEnabled, setWhatsappEnabled] = useState(false);
  const [whatsappRecipient, setWhatsappRecipient] = useState("");
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [emailTo, setEmailTo] = useState("");
  const [smtpHost, setSmtpHost] = useState("");
  const [strategyName, setStrategyName] = useState("rent-and-utilities");
  const [scoreThreshold, setScoreThreshold] = useState(80);
  const [minRewardRisk, setMinRewardRisk] = useState(1.2);
  const [maxAtrPct, setMaxAtrPct] = useState(3.5);
  const [imbalanceRatio, setImbalanceRatio] = useState(3);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!config) return;
    setAssetPool(config.asset_pool.join(","));
    setRisk(config.risk_per_trade);
    setTelegramEnabled(config.notification_config.telegram_enabled);
    setTelegramChatId(config.notification_config.telegram_chat_id ?? "");
    setWhatsappEnabled(config.notification_config.whatsapp_enabled);
    setWhatsappRecipient(config.notification_config.whatsapp_recipient ?? "");
    setEmailEnabled(config.notification_config.email_enabled);
    setEmailTo(config.notification_config.email_to ?? "");
    setSmtpHost(config.notification_config.smtp_host ?? "");
  }, [config]);

  useEffect(() => {
    if (!strategy) return;
    setStrategyName(strategy.name);
    setScoreThreshold(strategy.score_threshold);
    setMinRewardRisk(strategy.min_net_reward_risk);
    setMaxAtrPct(strategy.max_atr_pct * 100);
    setImbalanceRatio(strategy.orderbook_imbalance_ratio);
  }, [strategy]);

  const mode = config?.operation_mode ?? "SIGNAL_ONLY";
  const activePerformance = strategy
    ? performance.find((item) => item.strategy_config_id === strategy.id)
    : undefined;
  const assetTags = useMemo(() => normalizeAssets(assetPool), [assetPool]);

  async function saveConfig(nextMode?: OperationMode) {
    if (!config) return;
    setSaving(true);
    try {
      const updated = await api.updateConfig({
        operation_mode: nextMode ?? config.operation_mode,
        asset_pool: assetTags.length === 0 ? ["ALL"] : assetTags,
        risk_per_trade: risk,
        notification_config: {
          ...config.notification_config,
          telegram_enabled: telegramEnabled,
          telegram_chat_id: telegramChatId || null,
          whatsapp_enabled: whatsappEnabled,
          whatsapp_recipient: whatsappRecipient || null,
          email_enabled: emailEnabled,
          email_to: emailTo || null,
          smtp_host: smtpHost || null
        }
      });
      onConfigChange(updated);
    } finally {
      setSaving(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await Promise.all([saveConfig(), saveStrategy()]);
    } finally {
      setSaving(false);
    }
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

  return (
    <div className="shrink-0 border-b border-outline-variant bg-surface">
      <header className="flex min-h-12 items-center justify-between gap-md border-b border-outline-variant px-md py-sm lg:h-12 lg:py-0">
        <div className="flex min-w-0 items-center gap-lg">
          <div className="min-w-0">
            <div className="truncate font-h2 text-h2 text-on-surface">Deterministic Harmonic Sentinel</div>
          </div>
          <nav className="hidden items-center gap-md md:flex">
            {(["SIGNAL_ONLY", "AUTO_TRADE"] as OperationMode[]).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => saveConfig(item)}
                className={`px-sm py-xs font-label-caps text-label-caps transition ${
                  mode === item
                    ? "border-b-2 border-primary-container text-primary-container"
                    : "text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface"
                }`}
              >
                {item === "SIGNAL_ONLY" ? "Signal Only" : "Auto-Trade"}
              </button>
            ))}
          </nav>
        </div>

        <div className="flex min-w-0 items-center gap-sm lg:gap-md">
          <div className="hidden items-center gap-xs border border-outline-variant bg-surface-container-low px-sm py-xs sm:flex">
            <span className="label-caps opacity-60">Strat</span>
            <span className="max-w-40 truncate font-data-mono text-data-mono text-primary-fixed-dim">
              {strategy?.name ?? "loading"}
            </span>
          </div>
          <label className="hidden items-center gap-xs border border-outline-variant bg-surface-container-low px-sm py-xs lg:flex">
            <span className="label-caps opacity-60">Risk</span>
            <input
              type="number"
              min="0.01"
              max="25"
              step="0.1"
              value={risk}
              onChange={(event) => setRisk(Number(event.target.value))}
              className="w-14 border-0 bg-transparent p-0 text-right font-data-mono text-data-mono text-on-surface"
            />
            <span className="font-data-mono text-[11px] text-on-surface-variant">%</span>
          </label>
          <div className="hidden -space-x-2 lg:flex">
            {assetTags.slice(0, 4).map((asset) => (
              <span
                key={asset}
                className="flex h-6 w-6 items-center justify-center rounded-full border border-outline-variant bg-surface-container-highest font-data-mono text-[9px]"
              >
                {asset.slice(0, 3)}
              </span>
            ))}
          </div>
          <button
            type="button"
            onClick={panic}
            className="flex items-center gap-xs bg-secondary-container px-md py-xs font-label-caps text-label-caps text-on-secondary-container transition hover:brightness-110"
          >
            Panic
          </button>
          <div className="hidden items-center gap-sm border-l border-outline-variant pl-md text-on-surface-variant md:flex">
            <span className="font-data-mono text-[11px]">SENSORS</span>
            <span className="font-data-mono text-[11px]">SETTINGS</span>
          </div>
        </div>
      </header>

      <form onSubmit={submit} className="bg-background p-gutter">
        <div className="grid max-h-[42vh] grid-cols-12 gap-gutter overflow-y-auto bg-outline-variant/40 xl:max-h-none">
          <section className="col-span-12 bg-surface-container-lowest p-module-padding lg:col-span-4">
            <div className="mb-md flex items-end justify-between gap-md">
              <div>
                <div className="label-caps opacity-50">Workspace / Harmonic Sentinel</div>
                <h1 className="mt-xs font-h1 text-h1 text-on-surface">Strategy Runtime</h1>
              </div>
              <span className="hidden h-2 w-2 rounded-full bg-primary-container shadow-[0_0_12px_rgba(0,255,148,0.75)] sm:block" />
            </div>

            <div className="grid gap-md md:grid-cols-2 lg:grid-cols-1 2xl:grid-cols-2">
              <Field label="Active Strategy">
                <select
                  value={strategy?.id ?? ""}
                  onChange={(event) => activateStrategy(Number(event.target.value))}
                  className="w-full border border-outline-variant bg-surface-container-low p-sm font-data-mono text-data-mono text-on-surface"
                >
                  {strategies.length === 0 && <option value="">Loading strategies</option>}
                  {strategies.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.active ? "* " : ""}
                      {item.name}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Profile Name">
                <input
                  value={strategyName}
                  onChange={(event) => setStrategyName(event.target.value)}
                  className="w-full border border-outline-variant bg-surface-container-low p-sm font-data-mono text-data-mono text-on-surface"
                />
              </Field>

              <Field label="Asset Pool Focus">
                <input
                  value={assetPool}
                  onChange={(event) => setAssetPool(event.target.value)}
                  placeholder="BTC,ETH,SOL or ALL"
                  className="w-full border border-outline-variant bg-surface-container-low p-sm font-data-mono text-data-mono text-primary-fixed-dim"
                />
              </Field>

              <Field label="Risk Per Trade">
                <div className="flex items-center gap-sm border border-outline-variant bg-surface-container-low px-sm">
                  <input
                    type="number"
                    min="0.01"
                    max="25"
                    step="0.1"
                    value={risk}
                    onChange={(event) => setRisk(Number(event.target.value))}
                    className="w-full border-0 bg-transparent py-sm font-data-mono text-h2 text-tertiary-fixed-dim"
                  />
                  <span className="label-caps">Percent</span>
                </div>
              </Field>
            </div>
          </section>

          <section className="col-span-12 bg-surface-container-lowest lg:col-span-4">
            <div className="module-header flex items-center justify-between">
              <span>Quality Gates</span>
              <span className="font-data-mono text-[10px] text-primary-fixed-dim">
                {activePerformance?.degraded ? "DEGRADED" : "HEALTHY"}
              </span>
            </div>
            <div className="grid gap-md p-module-padding sm:grid-cols-2">
              <Dial label="Score Threshold" value={scoreThreshold} min={1} max={100} onChange={setScoreThreshold} suffix="/100" />
              <Dial label="Min R:R Ratio" value={minRewardRisk} min={0.1} max={10} step={0.1} onChange={setMinRewardRisk} />
              <Dial label="Max ATR %" value={maxAtrPct} min={0.1} max={20} step={0.1} onChange={setMaxAtrPct} suffix="%" />
              <Dial label="Orderbook L2 x" value={imbalanceRatio} min={1} max={20} step={0.1} onChange={setImbalanceRatio} />
            </div>
            <div className="grid grid-cols-3 gap-gutter border-t border-outline-variant bg-outline-variant/40">
              <Kpi label="Win Rate" value={activePerformance ? `${(activePerformance.win_rate * 100).toFixed(1)}%` : "--"} />
              <Kpi label="Profit Factor" value={activePerformance ? activePerformance.profit_factor.toFixed(2) : "--"} />
              <Kpi
                label="Max Drawdown"
                value={activePerformance ? `${activePerformance.max_drawdown_r.toFixed(1)}R` : "--"}
                tone="danger"
              />
            </div>
          </section>

          <section className="col-span-12 bg-surface-container-lowest lg:col-span-4">
            <div className="module-header flex items-center justify-between">
              <span>Notification Pipelines</span>
              <span className="font-data-mono text-[10px] text-tertiary-fixed-dim">V4_AUTH_OK</span>
            </div>
            <div className="grid gap-gutter bg-outline-variant/40 md:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
              <NotificationCard
                title="Telegram"
                state={telegramEnabled ? "Active" : "Muted"}
                enabled={telegramEnabled}
                onToggle={setTelegramEnabled}
              >
                <input
                  value={telegramChatId}
                  onChange={(event) => setTelegramChatId(event.target.value)}
                  className="w-full border border-outline-variant bg-surface-container-lowest p-sm font-data-mono text-[12px]"
                  placeholder="Chat id override"
                />
              </NotificationCard>

              <NotificationCard
                title="WhatsApp"
                state={whatsappEnabled ? "Linked" : "Standby"}
                enabled={whatsappEnabled}
                onToggle={setWhatsappEnabled}
              >
                <input
                  value={whatsappRecipient}
                  onChange={(event) => setWhatsappRecipient(event.target.value)}
                  className="w-full border border-outline-variant bg-surface-container-lowest p-sm font-data-mono text-[12px]"
                  placeholder="Phone or JID"
                />
              </NotificationCard>

              <NotificationCard title="Email" state={emailEnabled ? "Online" : "Offline"} enabled={emailEnabled} onToggle={setEmailEnabled}>
                <input
                  value={emailTo}
                  onChange={(event) => setEmailTo(event.target.value)}
                  className="mb-xs w-full border border-outline-variant bg-surface-container-lowest p-sm font-data-mono text-[12px]"
                  placeholder="Recipient"
                />
                <input
                  value={smtpHost}
                  onChange={(event) => setSmtpHost(event.target.value)}
                  className="w-full border border-outline-variant bg-surface-container-lowest p-sm font-data-mono text-[12px]"
                  placeholder="SMTP host"
                />
              </NotificationCard>
            </div>
          </section>

          <section className="col-span-12 flex flex-wrap items-center justify-between gap-md bg-surface p-module-padding">
            <div className="flex flex-wrap items-center gap-md">
              <StatusPill label="Hyperliquid" value="Connected" tone="success" />
              <StatusPill label="Engine" value={mode === "AUTO_TRADE" ? "Auto Trade" : "Signal Only"} tone="success" />
              <StatusPill
                label="Replay"
                value={activePerformance ? `${activePerformance.sample_size} samples` : "No snapshot"}
                tone={activePerformance?.degraded ? "danger" : "default"}
              />
            </div>
            <div className="flex flex-wrap gap-sm">
              <button
                type="button"
                onClick={saveAsNewStrategy}
                disabled={!strategy}
                className="border border-outline-variant bg-surface-container px-md py-sm font-label-caps text-label-caps text-on-surface transition hover:bg-surface-container-high disabled:opacity-50"
              >
                Save as New Profile
              </button>
              <button
                type="button"
                onClick={replayActiveStrategy}
                disabled={!strategy}
                className="border border-tertiary-fixed-dim bg-tertiary-fixed-dim/10 px-md py-sm font-label-caps text-label-caps text-tertiary-fixed-dim transition hover:bg-tertiary-fixed-dim/20 disabled:opacity-50"
              >
                Replay Strategy
              </button>
              <button
                type="submit"
                disabled={saving || !config || !strategy}
                className="bg-primary-container px-lg py-sm font-label-caps text-label-caps text-on-primary-container transition hover:brightness-110 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </section>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-xs block font-label-caps text-label-caps uppercase text-on-surface-variant opacity-70">{label}</span>
      {children}
    </label>
  );
}

function Dial({
  label,
  value,
  min,
  max,
  step = 1,
  suffix = "",
  onChange
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="border border-outline-variant/40 bg-surface-container-low p-sm">
      <span className="label-caps mb-xs block opacity-70">{label}</span>
      <div className="mb-sm flex items-baseline gap-xs">
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          className="w-20 border-0 bg-transparent p-0 font-data-mono text-h2 text-tertiary-fixed-dim"
        />
        {suffix && <span className="font-data-mono text-[11px] text-on-surface-variant">{suffix}</span>}
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-gutter w-full accent-primary-container"
      />
    </label>
  );
}

function NotificationCard({
  title,
  state,
  enabled,
  onToggle,
  children
}: {
  title: string;
  state: string;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  children: ReactNode;
}) {
  return (
    <div className="bg-surface-container-low p-module-padding">
      <div className="mb-md flex items-start justify-between gap-sm">
        <div>
          <div className="font-label-caps text-label-caps uppercase text-on-surface">{title}</div>
          <div className={`mt-xs font-data-mono text-[11px] ${enabled ? "text-primary-container" : "text-secondary"}`}>{state}</div>
        </div>
        <label className="relative inline-flex cursor-pointer items-center">
          <input className="peer sr-only" type="checkbox" checked={enabled} onChange={(event) => onToggle(event.target.checked)} />
          <span className="h-5 w-9 bg-surface-container-highest transition after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:bg-on-surface after:transition peer-checked:bg-primary-container peer-checked:after:translate-x-4" />
        </label>
      </div>
      {children}
    </div>
  );
}

function Kpi({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "danger" }) {
  return (
    <div className="bg-surface-container-lowest p-module-padding">
      <div className="label-caps opacity-60">{label}</div>
      <div className={`mt-xs font-data-mono text-data-mono ${tone === "danger" ? "text-secondary" : "text-primary-container"}`}>
        {value}
      </div>
    </div>
  );
}

function StatusPill({ label, value, tone }: { label: string; value: string; tone: "success" | "danger" | "default" }) {
  const color = tone === "success" ? "bg-primary-container" : tone === "danger" ? "bg-secondary" : "bg-tertiary-fixed-dim";
  return (
    <div className="flex items-center gap-sm border border-outline-variant bg-surface-container-low px-sm py-xs">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      <span className="font-label-caps text-[10px] uppercase text-on-surface-variant">{label}:</span>
      <span className="font-data-mono text-[11px] text-on-surface">{value}</span>
    </div>
  );
}

function normalizeAssets(input: string): string[] {
  const trimmed = input.trim().toUpperCase();
  if (trimmed === "ALL") return ["ALL"];
  return trimmed
    .split(",")
    .map((asset) => asset.trim())
    .filter(Boolean);
}
