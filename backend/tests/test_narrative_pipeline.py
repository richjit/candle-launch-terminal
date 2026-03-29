# backend/tests/test_narrative_pipeline.py
import pytest
from app.narrative.pipeline import compute_lifecycle


def test_lifecycle_emerging():
    assert compute_lifecycle(token_count=3, avg_gain=50.0, prev_volume=1000, curr_volume=2000) == "emerging"


def test_lifecycle_trending():
    assert compute_lifecycle(token_count=8, avg_gain=100.0, prev_volume=5000, curr_volume=8000) == "trending"


def test_lifecycle_saturated():
    assert compute_lifecycle(token_count=20, avg_gain=10.0, prev_volume=50000, curr_volume=45000) == "saturated"


def test_lifecycle_fading():
    assert compute_lifecycle(token_count=5, avg_gain=-20.0, prev_volume=50000, curr_volume=10000) == "fading"
