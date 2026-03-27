# backend/tests/test_zscore.py
import pytest
from app.analysis.zscore import compute_zscore, classify_zscore

def test_zscore_normal():
    values = [10, 12, 11, 13, 10, 12, 11, 12, 11, 10]
    z = compute_zscore(values, current=12)
    assert -2 < z < 2  # Normal range

def test_zscore_high_anomaly():
    values = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]
    z = compute_zscore(values, current=20)
    assert z > 2

def test_zscore_low_anomaly():
    values = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]
    z = compute_zscore(values, current=0)
    assert z < -2

def test_zscore_insufficient_data():
    z = compute_zscore([10], current=10)
    assert z == 0.0

def test_classify_bullish():
    assert classify_zscore(2.5) == 1

def test_classify_bearish():
    assert classify_zscore(-2.5) == -1

def test_classify_neutral():
    assert classify_zscore(0.5) == 0
