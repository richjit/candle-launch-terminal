// frontend/src/components/common/LastUpdated.tsx
interface LastUpdatedProps {
  timestamp: string | null;
}

export default function LastUpdated({ timestamp }: LastUpdatedProps) {
  if (!timestamp) return null;
  const date = new Date(timestamp);
  const timeStr = date.toLocaleTimeString();
  return (
    <span className="text-xs text-terminal-muted animate-pulse">
      Last updated: {timeStr}
    </span>
  );
}
