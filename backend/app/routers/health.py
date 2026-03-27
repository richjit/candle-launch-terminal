# backend/app/routers/health.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])

# Will be populated with fetcher references at app startup
_fetchers: list = []


def set_fetchers(fetchers: list):
    global _fetchers
    _fetchers = fetchers


@router.get("")
async def health():
    return {
        "status": "ok",
        "sources": [f.status() for f in _fetchers],
    }
