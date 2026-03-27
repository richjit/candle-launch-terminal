from datetime import datetime, timezone

from fastapi import APIRouter

from app.analysis.correlation import CorrelationResult

router = APIRouter(prefix="/api/pulse", tags=["pulse-correlations"])

_correlations: list[CorrelationResult] = []
_last_computed: datetime | None = None


def set_correlations(correlations: list[CorrelationResult], computed_at: datetime | None = None):
    global _correlations, _last_computed
    _correlations = correlations
    _last_computed = computed_at or datetime.now(timezone.utc)


@router.get("/correlations")
async def get_correlations():
    factors = [
        {
            "name": r.name,
            "label": r.label,
            "correlation": r.correlation,
            "optimal_lag_days": r.optimal_lag_days,
            "weight": r.weight,
            "in_score": r.in_score,
        }
        for r in _correlations
    ]
    return {
        "factors": factors,
        "last_computed": _last_computed.isoformat() if _last_computed else None,
    }
