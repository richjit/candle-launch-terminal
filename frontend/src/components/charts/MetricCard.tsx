// frontend/src/components/charts/MetricCard.tsx
interface MetricCardProps {
  label: string;
  value: string | number | null;
  subValue?: string;
  changePercent?: number;
}

export default function MetricCard({ label, value, subValue, changePercent }: MetricCardProps) {
  return (
    <div className="bg-terminal-card border border-terminal-border p-4">
      <div className="text-xs text-terminal-muted uppercase tracking-wider">{label}</div>
      <div className="mt-1 text-xl font-bold text-terminal-text">
        {value ?? "—"}
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs">
        {changePercent !== undefined && (
          <span className={changePercent >= 0 ? "text-terminal-green" : "text-terminal-red"}>
            {changePercent >= 0 ? "+" : ""}
            {changePercent.toFixed(1)}%
          </span>
        )}
        {subValue && <span className="text-terminal-muted">{subValue}</span>}
      </div>
    </div>
  );
}
