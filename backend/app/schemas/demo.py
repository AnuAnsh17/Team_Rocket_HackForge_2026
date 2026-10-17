"""Demo-mode DTOs.

These routes exist only when DEMO_MODE is true and APP_ENV is not production.
When demo mode is off they are not registered at all, so they answer 404 rather
than advertising their existence. Every response says plainly that the data is
synthetic.
"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiModel


class DemoSeedResponse(ApiModel):
    dataset: str = Field(
        ..., description="Identifier of the synthetic fixture set that was loaded."
    )
    synthetic: bool = Field(
        True, description="Always true. No real receipt or employee data is ever seeded."
    )
    organizations: int = Field(..., ge=0)
    users: int = Field(..., ge=0)
    memberships: int = Field(..., ge=0)
    claim_scenarios_seeded: int = Field(
        0, ge=0, description="Deterministic synthetic workflow scenarios created by the seed."
    )
    policy_rules_activated: int = Field(
        0,
        ge=0,
        description=(
            "Normally zero. A separate, explicitly enabled local synthetic fixture may activate "
            "one clearly labelled fictional rule; it is not company policy and is never loaded "
            "unless DEMO_SYNTHETIC_POLICY_ENABLED=true in development/test demo mode."
        ),
    )
    notes: list[str] = Field(default_factory=list)


class DemoResetResponse(ApiModel):
    dataset: str
    organizations_removed: int = Field(..., ge=0)
    users_removed: int = Field(..., ge=0)
    notes: list[str] = Field(default_factory=list)
