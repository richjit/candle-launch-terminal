import type { CorrelationFactor } from "../../types/pulse";

interface ScoredFactorsProps {
  factors: CorrelationFactor[];
}

export default function ScoredFactors({ factors }: ScoredFactorsProps) {
  const scored = factors.filter((f) => f.in_score);
  if (scored.length === 0) return null;

  return (
    <div className="bg-terminal-card border border-terminal-border p-4">
      <h3 className="text-sm font-bold text-terminal-accent mb-3 uppercase tracking-wider">
        Scored Factors
      </h3>
      <div className="space-y-3">
        {scored.map((f) => (
          <div key={f.name} className="flex items-center justify-between text-xs">
            <div>
              <div className="text-terminal-text font-medium">{f.label}</div>
              <div className="text-terminal-muted">
                r = {f.correlation > 0 ? "+" : ""}
                {f.correlation.toFixed(3)} · lag {f.optimal_lag_days}d
              </div>
            </div>
            <div className="text-right">
              <div className="text-terminal-text">
                {(f.weight * 100).toFixed(1)}% weight
              </div>
              <div className={f.correlation > 0 ? "text-terminal-green" : "text-terminal-red"}>
                {f.correlation > 0 ? "Bullish signal" : "Bearish signal"}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
