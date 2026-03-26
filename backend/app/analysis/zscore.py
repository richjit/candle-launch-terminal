# backend/app/analysis/zscore.py
import math


def compute_zscore(values: list[float], current: float) -> float:
    """Compute z-score of current value against historical values."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance)
    if std == 0:
        # All values identical: any deviation is infinitely anomalous
        if current > mean:
            return float("inf")
        elif current < mean:
            return float("-inf")
        return 0.0
    return (current - mean) / std


def classify_zscore(z: float, threshold: float = 1.5) -> int:
    """Classify z-score as bullish (+1), neutral (0), or bearish (-1)."""
    if z > threshold:
        return 1
    elif z < -threshold:
        return -1
    return 0
