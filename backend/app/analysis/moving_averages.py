# backend/app/analysis/moving_averages.py


def moving_average(values: list[float], window: int) -> list[float]:
    """Compute simple moving average."""
    if len(values) < window:
        return []
    result = []
    for i in range(len(values) - window + 1):
        window_slice = values[i : i + window]
        result.append(sum(window_slice) / window)
    return result


def detect_crossover(short_ma: list[float], long_ma: list[float]) -> str:
    """Detect crossover between short and long moving averages."""
    if len(short_ma) < 2 or len(long_ma) < 2:
        return "neutral"

    # Align to same length
    min_len = min(len(short_ma), len(long_ma))
    short = short_ma[-min_len:]
    long_ = long_ma[-min_len:]

    prev_diff = short[-2] - long_[-2]
    curr_diff = short[-1] - long_[-1]

    if prev_diff <= 0 and curr_diff > 0:
        return "bullish"
    elif prev_diff >= 0 and curr_diff < 0:
        return "bearish"
    return "neutral"
