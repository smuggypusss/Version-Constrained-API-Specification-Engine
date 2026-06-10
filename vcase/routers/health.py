from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict:
    """Kubernetes liveness probe. Returns 200 if the process is alive."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness() -> dict:
    """Kubernetes readiness probe. Returns 200 only when the app is ready to serve traffic."""
    return {"status": "ready"}
