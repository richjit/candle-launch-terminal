# backend/app/analysis/scores.py
import math
from dataclasses import dataclass, field


@dataclass
class ScoreFactor:
    name: str
    value: float
    z_score: float
    weight: float = 1.0
    label: str = ""


@dataclass
class CompositeScoreResult:
    score: float  # 0-100
    factors_available: int
    factors_total: int
    factors: list[dict]


def compute_health_score(factors: list[ScoreFactor], total_expected: int | None = None) -> CompositeScoreResult:
    """Compute Solana Health Score (0-100) from weighted z-score factors.

    Z-scores are mapped to a 0-100 scale:
    - z=0 maps to 50 (neutral)
    - z=+3 maps to ~95 (very bullish)
    - z=-3 maps to ~5 (very bearish)
    Uses sigmoid-like scaling: score = 50 + 50 * tanh(z / 2)
    """
    if not factors:
        return CompositeScoreResult(
            score=50.0,
            factors_available=0,
            factors_total=total_expected or 0,
            factors=[],
        )

    total_weight = sum(f.weight for f in factors)
    weighted_z = sum(f.z_score * f.weight for f in factors) / total_weight

    # Sigmoid mapping: z-score → 0-100
    raw_score = 50 + 50 * math.tanh(weighted_z / 2)
    clamped_score = max(0, min(100, raw_score))

    factor_details = []
    for f in factors:
        contribution = 50 * math.tanh(f.z_score / 2) * (f.weight / total_weight)
        factor_details.append({
            "name": f.name,
            "value": f.value,
            "z_score": round(f.z_score, 2),
            "normalized": round(math.tanh(f.z_score / 2), 2),
            "contribution": round(contribution, 2),
            "label": f.label or f.name,
        })

    return CompositeScoreResult(
        score=round(clamped_score, 1),
        factors_available=len(factors),
        factors_total=total_expected or len(factors),
        factors=factor_details,
    )
