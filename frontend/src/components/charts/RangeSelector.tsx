import type { ChartRange } from "../../types/pulse";

interface RangeSelectorProps {
  selected: ChartRange;
  onChange: (range: ChartRange) => void;
}

const RANGES: { value: ChartRange; label: string }[] = [
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "1y", label: "1Y" },
  { value: "all", label: "All" },
];

export default function RangeSelector({ selected, onChange }: RangeSelectorProps) {
  return (
    <div className="flex gap-1">
      {RANGES.map((r) => (
        <button
          key={r.value}
          onClick={() => onChange(r.value)}
          className={`px-3 py-1 text-xs font-mono border transition-colors ${
            selected === r.value
              ? "bg-terminal-accent text-black border-terminal-accent"
              : "bg-terminal-card text-terminal-muted border-terminal-border hover:border-terminal-accent"
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}
