"""Identity, membership and role DTOs.

These DTOs are deliberately narrow. An employee response never exposes another
employee's identifiers, and no DTO carries a permission list that a client could
be tempted to trust - permissions are enforced server-side only.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import Field

from app.core.enums import MembershipStatus, RoleCode
from app.schemas.common import ApiModel


class UserSummary(ApiModel):
    """Minimal, safe representation of a person."""

    id: uuid.UUID
    display_name: str
    is_active: bool = True


class MembershipSummary(ApiModel):
    """An employee's organizational position, as needed for display and routing."""

    id: uuid.UUID
    organization_id: uuid.UUID
    user: UserSummary
    employee_code: str | None = None
    status: MembershipStatus
    department_name: str | None = None
    cost_center_name: str | None = None
    office_location_name: str | None = None
    job_grade_name: str | None = Field(
        default=None,
        description=(
            "Grade label only. Never used by a client to infer an allowance: the "
            "effective allowance comes from the resolved policy assignment."
        ),
    )
    manager_membership_id: uuid.UUID | None = None
    joined_on: date | None = None


class RoleAssignmentSummary(ApiModel):
    """A granted role, with the scope it applies to."""

    id: uuid.UUID
    role: RoleCode
    scope_type: str = Field(
        ..., description="organization | department | cost_center | team | self"
    )
    scope_id: uuid.UUID
    granted_at: date | None = None
    revoked_at: date | None = None
