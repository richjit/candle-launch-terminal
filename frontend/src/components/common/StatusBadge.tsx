// frontend/src/components/common/StatusBadge.tsx
interface StatusBadgeProps {
  status: "live" | "stale" | "unavailable";
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const styles = {
    live: "bg-terminal-green/20 text-terminal-green",
    stale: "bg-terminal-accent/20 text-terminal-accent",
    unavailable: "bg-terminal-red/20 text-terminal-red",
  };
  return (
    <span className={`text-xs px-2 py-0.5 ${styles[status]}`}>
      {status.toUpperCase()}
    </span>
  );
}
