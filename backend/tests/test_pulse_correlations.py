import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.analysis.correlation import CorrelationResult
from app.routers.pulse_correlations import router, set_correlations


def _make_app():
    app = FastAPI()
    app.include_router(router)
    return app


def test_correlations_endpoint_returns_factors():
    mock_correlations = [
        CorrelationResult(name="tvl", label="Total Value Locked", correlation=0.42, optimal_lag_days=3, weight=0.55, in_score=True),
        CorrelationResult(name="fear_greed", label="Fear & Greed Index", correlation=0.34, optimal_lag_days=7, weight=0.45, in_score=True),
    ]
    set_correlations(mock_correlations, datetime(2026, 3, 27, tzinfo=timezone.utc))

    client = TestClient(_make_app())
    resp = client.get("/api/pulse/correlations")
    assert resp.status_code == 200
    data = resp.json()

    assert "factors" in data
    assert len(data["factors"]) == 2
    assert data["factors"][0]["name"] == "tvl"
    assert data["factors"][0]["correlation"] == 0.42
    assert data["factors"][0]["weight"] == 0.55
    assert data["factors"][0]["in_score"] is True
    assert "last_computed" in data


def test_correlations_endpoint_empty():
    set_correlations([], datetime(2026, 3, 27, tzinfo=timezone.utc))

    client = TestClient(_make_app())
    resp = client.get("/api/pulse/correlations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["factors"] == []
