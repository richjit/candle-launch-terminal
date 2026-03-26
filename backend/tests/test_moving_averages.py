# backend/tests/test_moving_averages.py
import pytest
from app.analysis.moving_averages import moving_average, detect_crossover

def test_moving_average():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    ma = moving_average(values, window=3)
    assert ma == pytest.approx([2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])

def test_moving_average_insufficient():
    values = [1, 2]
    ma = moving_average(values, window=5)
    assert ma == []

def test_crossover_bullish():
    # short crosses above long between second-to-last and last element
    short_ma = [1, 2, 3, 3.5, 5]
    long_ma = [2, 3, 4, 4, 4]
    # prev_diff = 3.5 - 4 = -0.5 (below), curr_diff = 5 - 4 = 1 (above) → bullish
    signal = detect_crossover(short_ma, long_ma)
    assert signal == "bullish"

def test_crossover_bearish():
    # short crosses below long between second-to-last and last element
    short_ma = [7, 5, 4.5, 4, 2]
    long_ma = [4, 4, 4, 3, 3]
    # prev_diff = 4 - 3 = 1 (above), curr_diff = 2 - 3 = -1 (below) → bearish
    signal = detect_crossover(short_ma, long_ma)
    assert signal == "bearish"

def test_crossover_neutral():
    short_ma = [3, 3, 3]
    long_ma = [3, 3, 3]
    signal = detect_crossover(short_ma, long_ma)
    assert signal == "neutral"
