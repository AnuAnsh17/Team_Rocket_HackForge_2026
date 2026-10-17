"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse
from app.services.health_service import build_health_report

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description=(
        "Reports service health, the database probe result and the status of each "
        "dependency. Contains no secrets, no connection strings and no stack traces. "
        "Unauthenticated by design so a load balancer can reach it."
    ),
)
def health() -> HealthResponse:
    return build_health_report(settings)
