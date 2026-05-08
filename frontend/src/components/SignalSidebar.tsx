import type { Pattern } from "../types/api";

interface SignalSidebarProps {
  patterns: Pattern[];
  selectedPattern: Pattern | null;
  onSelect: (pattern: Pattern) => void;
}

export function SignalSidebar({ patterns, selectedPattern, onSelect }: SignalSidebarProps) {
  return (
    <aside className="w-full border-r border-slate-800 bg-slate-950 p-4 lg:w-80">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Active Signals</h2>
        <span className="rounded-full bg-cyan-400/10 px-3 py-1 text-xs font-semibold text-cyan-300">
          {patterns.length}
        </span>
      </div>

      <div className="space-y-3">
        {patterns.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-800 p-4 text-sm text-slate-400">
            No active signals yet. Pending patterns fire here after the confluence score reaches 80.
          </div>
        )}

        {patterns.map((pattern) => (
          <button
            key={pattern.id}
            onClick={() => onSelect(pattern)}
            className={`w-full rounded-xl border p-4 text-left transition ${
              selectedPattern?.id === pattern.id
                ? "border-cyan-400 bg-cyan-400/10"
                : "border-slate-800 bg-slate-900 hover:border-slate-600"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold text-white">{pattern.symbol}</span>
              <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-300">{pattern.timeframe}</span>
            </div>
            <p className="mt-2 text-sm text-slate-300">{pattern.pattern_type}</p>
            {pattern.confluence_details?.net_reward_risk !== undefined && (
              <p className="mt-1 text-xs text-slate-400">
                Net R:R {pattern.confluence_details.net_reward_risk.toFixed(2)} | ATR{" "}
                {((pattern.confluence_details.atr_pct ?? 0) * 100).toFixed(2)}%
              </p>
            )}
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-cyan-400"
                style={{ width: `${pattern.confluence_score}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-slate-400">Score {pattern.confluence_score}/100</p>
            {pattern.confluence_details?.reasons?.slice(0, 2).map((reason) => (
              <p key={reason} className="mt-1 text-xs text-cyan-200">
                {reason}
              </p>
            ))}
          </button>
        ))}
      </div>
    </aside>
  );
}
