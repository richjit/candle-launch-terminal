interface Props {
  breakdown: Record<string, number | null>;
  formatValue?: (v: number | null) => string;
}

function defaultFormat(v: number | null): string {
  if (v === null || v === undefined) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  if (v < 1 && v > 0) return `${(v * 100).toFixed(1)}%`;
  return v.toLocaleString();
}

export default function LaunchBreakdownTable({ breakdown, formatValue = defaultFormat }: Props) {
  const entries = Object.entries(breakdown).sort(
    (a, b) => (b[1] ?? 0) - (a[1] ?? 0)
  );

  if (entries.length === 0) return null;

  return (
    <div className="mt-6">
      <h3 className="text-xs text-terminal-muted uppercase tracking-wide mb-3">
        By Launchpad
      </h3>
      <div className="bg-terminal-card border border-terminal-border rounded">
        {entries.map(([name, value]) => (
          <div
            key={name}
            className="flex items-center justify-between px-4 py-2 border-b border-terminal-border last:border-b-0"
          >
            <span className="text-sm text-terminal-text capitalize">{name}</span>
            <span className="text-sm font-mono text-terminal-accent">
              {formatValue(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
