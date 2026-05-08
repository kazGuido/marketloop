import type { Pattern } from "../types/api";

interface SignalSidebarProps {
  patterns: Pattern[];
  selectedPattern: Pattern | null;
  onSelect: (pattern: Pattern) => void;
}

export function SignalSidebar({ patterns, selectedPattern, onSelect }: SignalSidebarProps) {
  return (
    <aside className="flex max-h-[42vh] w-full shrink-0 flex-col border-l border-outline-variant bg-surface lg:max-h-none lg:w-80">
      <div className="module-header flex items-center justify-between">
        <span>Active Patterns</span>
        <span className="font-data-mono text-[10px] text-primary-fixed-dim">{patterns.length.toString().padStart(2, "0")}</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {patterns.length === 0 && (
          <div className="m-md border border-dashed border-outline-variant bg-surface-container-lowest p-md">
            <div className="font-label-caps text-label-caps uppercase text-on-surface">No active signals</div>
            <p className="mt-sm font-body-sm text-body-sm text-on-surface-variant">
              Pending patterns will surface here once confluence clears the configured score threshold.
            </p>
          </div>
        )}

        {patterns.map((pattern) => {
          const selected = selectedPattern?.id === pattern.id;
          const bullish = pattern.direction === "BULLISH";
          const scoreTone =
            pattern.confluence_score >= 80
              ? "text-primary-container"
              : pattern.confluence_score >= 60
                ? "text-tertiary-fixed-dim"
                : "text-secondary";

          return (
            <button
              key={pattern.id}
              type="button"
              onClick={() => onSelect(pattern)}
              className={`group relative w-full border-b border-outline-variant p-md text-left transition ${
                selected ? "bg-surface-container-high" : "bg-surface hover:bg-surface-container"
              }`}
            >
              <span
                className={`absolute left-0 top-0 h-full w-1 ${selected ? "bg-primary-container" : bullish ? "bg-primary-container/50" : "bg-secondary/70"}`}
              />
              <div className="mb-sm flex items-start justify-between gap-md">
                <div className="min-w-0">
                  <div className="truncate font-data-mono text-data-mono text-on-surface group-hover:text-primary-fixed-dim">
                    {pattern.symbol}
                  </div>
                  <div className="mt-xs font-body-sm text-[11px] text-on-surface-variant">
                    {pattern.timeframe} / {pattern.direction.toLowerCase()} {pattern.pattern_type}
                  </div>
                </div>
                <div className="text-right">
                  <div className={`font-h1 text-h1 ${scoreTone}`}>{pattern.confluence_score}</div>
                  <div className="font-label-caps text-[9px] uppercase text-on-surface-variant opacity-60">Conf. score</div>
                </div>
              </div>

              <div className="mb-sm grid grid-cols-2 gap-sm font-data-mono text-[11px]">
                <SignalDatum
                  label="R:R"
                  value={pattern.confluence_details?.net_reward_risk?.toFixed(2) ?? "--"}
                  tone="primary"
                />
                <SignalDatum label="ATR" value={`${((pattern.confluence_details?.atr_pct ?? 0) * 100).toFixed(2)}%`} />
                <SignalDatum label="L2" value={pattern.confluence_details?.imbalance_ratio?.toFixed(2) ?? "--"} />
                <SignalDatum
                  label="Funding"
                  value={
                    pattern.confluence_details?.funding_rate == null
                      ? "--"
                      : `${(pattern.confluence_details.funding_rate * 100).toFixed(3)}%`
                  }
                />
              </div>

              <div className="h-1.5 bg-surface-container-highest">
                <div className="h-full bg-primary-container" style={{ width: `${Math.min(pattern.confluence_score, 100)}%` }} />
              </div>

              <div className="mt-sm space-y-xs">
                {pattern.confluence_details?.reasons?.slice(0, 2).map((reason) => (
                  <div key={reason} className="flex items-start gap-xs font-body-sm text-[11px] text-on-surface-variant">
                    <span className="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full bg-primary-container" />
                    <span>{reason}</span>
                  </div>
                ))}
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}

function SignalDatum({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "primary" }) {
  return (
    <div className="flex justify-between gap-sm border border-outline-variant/30 bg-surface-container-lowest px-sm py-xs">
      <span className="text-on-surface-variant">{label}</span>
      <span className={tone === "primary" ? "text-primary-container" : "text-on-surface"}>{value}</span>
    </div>
  );
}
