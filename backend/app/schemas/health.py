"""Health response DTO.

The health endpoint is deliberately information-poor: it reports component
status codes, never a connection string, driver message, host name or version of
anything that would help an attacker.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel

ComponentStatus = Literal["ok", "unavailable", "not_configured", "not_implemented", "degraded"]


class HealthComponent(ApiModel):
    """Status of one dependency."""

    status: ComponentStatus
    detail: str | None = Field(
        default=None,
        description="Stable machine-readable code such as DATABASE_UNAVAILABLE. Never a raw error.",
    )
    latency_ms: float | None = Field(default=None, ge=0)


class HealthResponse(ApiModel):
    """Aggregate service health."""

    status: Literal["ok", "degraded", "unavailable"]
    app_version: str
    api_version: str = Field(..., description="Advertised API version prefix, for example v1.")
    environment: str
    demo_mode: bool = Field(
        ..., description="True when demo routes and the demo identity switcher are active."
    )
    checked_at: datetime
    components: dict[str, HealthComponent] = Field(
        ...,
        description="Per-dependency status keyed by a stable component name.",
    )
