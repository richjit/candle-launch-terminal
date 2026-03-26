// frontend/src/components/charts/TimeSeriesChart.tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

interface DataPoint {
  timestamp: string | number;
  value: number;
}

interface TimeSeriesChartProps {
  data: DataPoint[];
  label: string;
  color?: string;
  height?: number;
  formatValue?: (v: number) => string;
}

export default function TimeSeriesChart({
  data,
  label,
  color = "#f0b90b",
  height = 200,
  formatValue = (v) => v.toLocaleString(),
}: TimeSeriesChartProps) {
  if (data.length === 0) {
    return (
      <div className="bg-terminal-card border border-terminal-border p-4" style={{ height }}>
        <div className="text-xs text-terminal-muted uppercase tracking-wider mb-2">{label}</div>
        <div className="text-terminal-muted text-sm">No data available</div>
      </div>
    );
  }

  const chartData = data.map((d) => ({
    time: typeof d.timestamp === "number" ? new Date(d.timestamp * 1000).toLocaleDateString() : d.timestamp,
    value: d.value,
  }));

  return (
    <div className="bg-terminal-card border border-terminal-border p-4">
      <div className="text-xs text-terminal-muted uppercase tracking-wider mb-2">{label}</div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e1e2e" />
          <XAxis dataKey="time" tick={{ fill: "#6b7280", fontSize: 10 }} tickLine={false} />
          <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} tickLine={false} tickFormatter={formatValue} />
          <Tooltip
            contentStyle={{ backgroundColor: "#12121a", border: "1px solid #1e1e2e", color: "#e0e0e0", fontSize: 12 }}
            formatter={(value) => [typeof value === "number" ? formatValue(value) : String(value), label]}
          />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
