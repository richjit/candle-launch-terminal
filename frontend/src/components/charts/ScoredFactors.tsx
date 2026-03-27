import type { CorrelationFactor } from "../../types/pulse";

interface ScoredFactorsProps {
  factors: CorrelationFactor[];
  excludedFactors: Set<string>;
  onToggleFactor: (name: string) => void;
}

export default function ScoredFactors({ factors, excludedFactors, onToggleFactor }: ScoredFactorsProps) {
  if (factors.length === 0) return null;

  // Separate into eligible (passed threshold) and ineligible
  const eligible = factors.filter((f) => f.in_score);
  const ineligible = factors.filter((f) => !f.in_score);

  // Recalculate displayed weights based on currently active factors
  const active = eligible.filter((f) => !excludedFactors.has(f.name));
  const totalAbsR = active.reduce((sum, f) => sum + Math.abs(f.correlation), 0);

  return (
    <div className="bg-terminal-card border border-terminal-border p-4">
      <h3 className="text-sm font-bold text-terminal-accent mb-3 uppercase tracking-wider">
        Scored Factors
      </h3>
      <div className="space-y-2">
        {eligible.map((f) => {
          const isExcluded = excludedFactors.has(f.name);
          const displayWeight = isExcluded || totalAbsR === 0
            ? 0
            : Math.abs(f.correlation) / totalAbsR;

          return (
            <button
              key={f.name}
              onClick={() => onToggleFactor(f.name)}
              className={`w-full flex items-center justify-between text-xs p-2 rounded transition-colors ${
                isExcluded
                  ? "opacity-40 bg-terminal-card"
                  : "bg-terminal-bg/50 hover:bg-terminal-bg"
              }`}
            >
              <div className="flex items-center gap-2 text-left">
                <div
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    isExcluded ? "bg-terminal-muted" : "bg-terminal-accent"
                  }`}
                />
                <div>
                  <div className="text-terminal-text font-medium">{f.label}</div>
                  <div className="text-terminal-muted">
                    r = {f.correlation > 0 ? "+" : ""}
                    {f.correlation.toFixed(3)} · lag {f.optimal_lag_days}d
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-terminal-text">
                  {(displayWeight * 100).toFixed(1)}% weight
                </div>
                <div className={f.correlation > 0 ? "text-terminal-green" : "text-terminal-red"}>
                  {isExcluded ? "Excluded" : f.correlation > 0 ? "Bullish signal" : "Bearish signal"}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {ineligible.length > 0 && (
        <>
          <div className="text-xs text-terminal-muted mt-4 mb-2 uppercase tracking-wider">
            Below threshold (|r| &lt; 0.15)
          </div>
          <div className="space-y-1">
            {ineligible.map((f) => (
              <div key={f.name} className="flex items-center justify-between text-xs p-2 opacity-30">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-terminal-muted flex-shrink-0" />
                  <div>
                    <span className="text-terminal-text">{f.label}</span>
                    <span className="text-terminal-muted ml-2">
                      r = {f.correlation > 0 ? "+" : ""}{f.correlation.toFixed(3)}
                    </span>
                  </div>
                </div>
                <span className="text-terminal-muted">Not significant</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
