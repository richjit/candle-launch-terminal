// frontend/src/components/scores/ScoreCard.tsx
import { CompositeScore } from "../../types/api";

function scoreColor(score: number): string {
  if (score >= 70) return "text-terminal-green";
  if (score >= 40) return "text-terminal-accent";
  return "text-terminal-red";
}

function scoreLabel(score: number): string {
  if (score >= 70) return "Strong";
  if (score >= 55) return "Good";
  if (score >= 40) return "Neutral";
  if (score >= 25) return "Weak";
  return "Critical";
}

interface ScoreCardProps {
  title: string;
  score: CompositeScore | null;
}

export default function ScoreCard({ title, score }: ScoreCardProps) {
  if (!score) {
    return (
      <div className="bg-terminal-card border border-terminal-border p-6">
        <h2 className="text-sm text-terminal-muted uppercase tracking-wider">{title}</h2>
        <div className="text-terminal-muted mt-2">Loading...</div>
      </div>
    );
  }

  return (
    <div className="bg-terminal-card border border-terminal-border p-6">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm text-terminal-muted uppercase tracking-wider">{title}</h2>
        <span className="text-xs text-terminal-muted">
          {score.factors_available} of {score.factors_total} factors
        </span>
      </div>
      <div className="mt-3 flex items-baseline gap-3">
        <span className={`text-4xl font-bold ${scoreColor(score.score)}`}>
          {score.score}
        </span>
        <span className="text-lg text-terminal-muted">/ {score.max_score}</span>
        <span className={`text-sm ${scoreColor(score.score)}`}>
          {scoreLabel(score.score)}
        </span>
      </div>
      {/* Progress bar */}
      <div className="mt-3 h-1.5 bg-terminal-border overflow-hidden">
        <div
          className={`h-full transition-all duration-500 ${
            score.score >= 70 ? "bg-terminal-green" : score.score >= 40 ? "bg-terminal-accent" : "bg-terminal-red"
          }`}
          style={{ width: `${Math.min(100, (score.score / score.max_score) * 100)}%` }}
        />
      </div>
    </div>
  );
}
