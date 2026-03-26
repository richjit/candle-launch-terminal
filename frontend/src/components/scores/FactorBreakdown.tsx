// frontend/src/components/scores/FactorBreakdown.tsx
import { useState } from "react";
import { ScoreFactor } from "../../types/api";

interface FactorBreakdownProps {
  factors: ScoreFactor[];
}

export default function FactorBreakdown({ factors }: FactorBreakdownProps) {
  const [expanded, setExpanded] = useState(false);

  if (factors.length === 0) return null;

  return (
    <div className="bg-terminal-card border border-terminal-border">
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="w-full px-6 py-3 flex items-center justify-between text-sm text-terminal-muted hover:text-terminal-text transition-colors"
      >
        <span>Factor Breakdown</span>
        <span>{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <div className="px-6 pb-4 space-y-2">
          {factors.map((f) => (
            <div key={f.name} className="flex items-center gap-3 text-sm">
              <span className="w-40 text-terminal-muted truncate">{f.label || f.name}</span>
              <div className="flex-1 h-2 bg-terminal-border overflow-hidden">
                <div
                  className={`h-full ${
                    f.contribution > 0 ? "bg-terminal-green" : f.contribution < 0 ? "bg-terminal-red" : "bg-terminal-muted"
                  }`}
                  style={{ width: `${Math.min(100, Math.abs(f.normalized) * 100)}%` }}
                />
              </div>
              <span
                className={`w-16 text-right ${
                  f.contribution > 0 ? "text-terminal-green" : f.contribution < 0 ? "text-terminal-red" : "text-terminal-muted"
                }`}
              >
                {f.contribution > 0 ? "+" : ""}
                {f.contribution.toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
