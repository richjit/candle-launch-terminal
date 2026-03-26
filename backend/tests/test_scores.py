# backend/tests/test_scores.py
import pytest
from app.analysis.scores import compute_health_score, ScoreFactor

def test_health_score_all_bullish():
    factors = [
        ScoreFactor(name="tps", value=3000, z_score=2.0, weight=1.0),
        ScoreFactor(name="priority_fees", value=5000, z_score=1.8, weight=1.0),
        ScoreFactor(name="dex_volume", value=1e9, z_score=2.5, weight=1.5),
        ScoreFactor(name="tvl", value=5e9, z_score=1.0, weight=1.0),
        ScoreFactor(name="stablecoin_supply", value=3e7, z_score=0.5, weight=1.0),
        ScoreFactor(name="fear_greed", value=75, z_score=1.5, weight=0.5),
    ]
    result = compute_health_score(factors)
    assert result.score > 70
    assert result.factors_available == 6
    assert result.factors_total == 6

def test_health_score_all_bearish():
    factors = [
        ScoreFactor(name="tps", value=500, z_score=-2.5, weight=1.0),
        ScoreFactor(name="dex_volume", value=1e7, z_score=-3.0, weight=1.5),
        ScoreFactor(name="tvl", value=2e9, z_score=-2.0, weight=1.0),
    ]
    result = compute_health_score(factors)
    assert result.score < 30

def test_health_score_empty():
    result = compute_health_score([])
    assert result.score == 50  # neutral default
    assert result.factors_available == 0

def test_health_score_clamped():
    factors = [
        ScoreFactor(name="x", value=999, z_score=10.0, weight=5.0),
    ]
    result = compute_health_score(factors)
    assert 0 <= result.score <= 100
