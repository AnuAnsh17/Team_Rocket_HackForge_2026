"""Read-only dashboard analytics endpoints."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_actor, get_pagination, get_session
from app.core.enums import ExpenseStatus
from app.core.errors import ValidationFailed
from app.core.pagination import Pagination
from app.core.security import Actor
from app.schemas.analytics import (
    AnalyticsGroupBy,
    AnalyticsOverviewResponse,
    AnalyticsSpendResponse,
)
from app.schemas.common import CurrencyCode
from app.services import analytics_service
from app.services.analytics_service import AnalyticsFilters

router = APIRouter(tags=["analytics"], prefix="/analytics")


def get_analytics_filters(
    from_date: date = Query(
        ...,
        alias="from",
        description="Inclusive lower transaction-date boundary (YYYY-MM-DD).",
    ),
    to_date: date = Query(
        ...,
        alias="to",
        description="Inclusive upper transaction-date boundary (YYYY-MM-DD).",
    ),
    department_id: UUID | None = Query(default=None),
    office_location_id: UUID | None = Query(default=None),
    employee_membership_id: UUID | None = Query(
        default=None,
        description="Organization membership UUID; requires analytics:read_org.",
    ),
    category: str | None = Query(default=None, min_length=1, max_length=64),
    currency: CurrencyCode | None = Query(default=None),
    status: ExpenseStatus | None = Query(default=None),
) -> AnalyticsFilters:
    if from_date > to_date:
        raise ValidationFailed(
            "The from date must be on or before the to date.", details=[{"field": "from"}]
        )
    return AnalyticsFilters(
        from_date=from_date,
        to_date=to_date,
        department_id=department_id,
        office_location_id=office_location_id,
        employee_membership_id=employee_membership_id,
        category=category,
        currency=currency,
        status=status,
    )


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    summary="Read transaction-date dashboard overview",
    description=(
        "Returns organization-scoped counts and exact currency-separated aggregates for the "
        "inclusive expense_date range. Claims without expense_date are counted separately and "
        "are not assigned to the selected period. Approved is a workflow status, not a policy "
        "PASS or a payment record."
    ),
)
def get_overview(
    filters: AnalyticsFilters = Depends(get_analytics_filters),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> AnalyticsOverviewResponse:
    organization_id = analytics_service.require_analytics_access(actor)
    return analytics_service.overview(session, organization_id, filters)


@router.get(
    "/spend",
    response_model=AnalyticsSpendResponse,
    summary="Read filtered spend aggregation",
    description=(
        "Groups persisted expenses within the inclusive expense_date range by one selected "
        "dimension and currency. Missing transaction dates are excluded from groups and counted "
        "separately. Employee grouping/filtering requires analytics:read_org. Empty calendar "
        "months are omitted and therefore represent zero dated claims for that month."
    ),
)
def get_spend(
    group_by: AnalyticsGroupBy = Query(default=AnalyticsGroupBy.MONTH),
    filters: AnalyticsFilters = Depends(get_analytics_filters),
    pagination: Pagination = Depends(get_pagination),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> AnalyticsSpendResponse:
    employee_level = (
        group_by == AnalyticsGroupBy.EMPLOYEE or filters.employee_membership_id is not None
    )
    organization_id = analytics_service.require_analytics_access(
        actor, employee_level=employee_level
    )
    return analytics_service.spend(session, organization_id, filters, group_by, pagination)
