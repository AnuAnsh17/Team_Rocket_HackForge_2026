"""Database-side, tenant-scoped analytics queries.

Every monetary aggregate is grouped by the persisted transaction currency. The
service never joins one-to-many receipt, extraction, line-item, decision, finding,
or audit tables, so those records cannot multiply an expense in an aggregate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Date, and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import ExpenseFieldName, ExpenseStatus
from app.core.errors import Forbidden, ValidationFailed
from app.core.pagination import Pagination, build_page
from app.core.permissions import Permission
from app.core.security import Actor
from app.models.expense import Expense, ExpenseFieldEvidence
from app.models.identity import OrganizationMembership, User
from app.models.organization import Department, OfficeLocation
from app.schemas.analytics import (
    UNASSIGNED_BUCKET_KEY,
    AnalyticsCategoryAmount,
    AnalyticsDepartmentAmount,
    AnalyticsDepartmentRow,
    AnalyticsDepartmentSummaryResponse,
    AnalyticsDepartmentTotals,
    AnalyticsGroupBy,
    AnalyticsLocationAmount,
    AnalyticsMonthlyAmount,
    AnalyticsOverviewResponse,
    AnalyticsSpendMatrixResponse,
    AnalyticsSpendMatrixRow,
    AnalyticsSpendResponse,
    AnalyticsSpendRow,
    AnalyticsStatusAmount,
    AnalyticsStatusCount,
)


@dataclass(frozen=True, slots=True)
class AnalyticsFilters:
    from_date: date
    to_date: date
    department_id: uuid.UUID | None = None
    office_location_id: uuid.UUID | None = None
    employee_membership_id: uuid.UUID | None = None
    category: str | None = None
    currency: str | None = None
    status: ExpenseStatus | None = None


def require_analytics_access(actor: Actor, *, employee_level: bool = False) -> uuid.UUID:
    """Require both analytics permission and organization-wide expense scope."""
    if actor.active_organization_id is None or not actor.has(Permission.EXPENSE_READ_ORG_SCOPED):
        raise Forbidden("Organization-scoped analytics access is required.")
    if not (actor.has(Permission.ANALYTICS_READ) or actor.has(Permission.ANALYTICS_READ_ORG)):
        raise Forbidden("Analytics access is not granted to this actor.")
    if employee_level and not actor.has(Permission.ANALYTICS_READ_ORG):
        raise Forbidden("Employee-level analytics requires analytics:read_org.")
    try:
        return uuid.UUID(actor.active_organization_id)
    except ValueError as exc:
        raise Forbidden("An active organization membership is required.") from exc


def _validate_filters(
    session: Session, organization_id: uuid.UUID, filters: AnalyticsFilters
) -> None:
    checks = (
        (Department, filters.department_id, "department_id"),
        (OfficeLocation, filters.office_location_id, "office_location_id"),
        (OrganizationMembership, filters.employee_membership_id, "employee_membership_id"),
    )
    for model, identifier, field_name in checks:
        if identifier is None:
            continue
        present = session.execute(
            select(model.id).where(
                model.id == identifier,
                model.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if present is None:
            raise ValidationFailed(
                f"The selected {field_name} is not part of the active organization.",
                details=[{"field": field_name}],
            )


def _conditions(
    organization_id: uuid.UUID,
    filters: AnalyticsFilters,
    *,
    include_date_range: bool,
) -> list[Any]:
    conditions: list[Any] = [
        Expense.organization_id == organization_id,
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.id == Expense.membership_id,
    ]
    if include_date_range:
        conditions.extend(
            (
                Expense.expense_date >= filters.from_date,
                Expense.expense_date <= filters.to_date,
            )
        )
    if filters.department_id is not None:
        conditions.append(OrganizationMembership.department_id == filters.department_id)
    if filters.office_location_id is not None:
        conditions.append(OrganizationMembership.office_location_id == filters.office_location_id)
    if filters.employee_membership_id is not None:
        conditions.append(OrganizationMembership.id == filters.employee_membership_id)
    if filters.category is not None:
        conditions.append(Expense.category == filters.category)
    if filters.currency is not None:
        conditions.append(Expense.currency == filters.currency)
    if filters.status is not None:
        conditions.append(Expense.status == filters.status.value)
    return conditions


def _expense_statement(*columns: Any) -> Any:
    return (
        select(*columns)
        .select_from(Expense)
        .join(
            OrganizationMembership,
            OrganizationMembership.id == Expense.membership_id,
        )
    )


def _amount_values(row: Any) -> dict[str, Any]:
    return {
        "currency": row["currency"],
        "claim_count": row["claim_count"],
        "amount_claim_count": row["amount_claim_count"],
        "amount_total": row["amount_total"],
    }


def _amount_columns() -> tuple[Any, Any, Any]:
    return (
        func.count(Expense.id).label("claim_count"),
        func.count(Expense.amount).label("amount_claim_count"),
        func.sum(Expense.amount).label("amount_total"),
    )


def _status_amounts(
    session: Session, organization_id: uuid.UUID, filters: AnalyticsFilters
) -> list[AnalyticsStatusAmount]:
    claim_count, amount_claim_count, amount_total = _amount_columns()
    statement = _expense_statement(
        Expense.status.label("status"),
        Expense.currency.label("currency"),
        claim_count,
        amount_claim_count,
        amount_total,
    ).where(*_conditions(organization_id, filters, include_date_range=True))
    rows = session.execute(
        statement.group_by(Expense.status, Expense.currency).order_by(
            Expense.status, Expense.currency.asc().nullsfirst()
        )
    ).mappings()
    return [
        AnalyticsStatusAmount(status=ExpenseStatus(row["status"]), **_amount_values(row))
        for row in rows
    ]


def _overview_breakdown(
    session: Session,
    organization_id: uuid.UUID,
    filters: AnalyticsFilters,
    dimension: str,
) -> list[Any]:
    claim_count, amount_claim_count, amount_total = _amount_columns()
    if dimension == "department":
        statement = _expense_statement(
            Department.id.label("department_id"),
            Department.name.label("department_name"),
            Expense.currency.label("currency"),
            claim_count,
            amount_claim_count,
            amount_total,
        ).outerjoin(
            Department,
            and_(
                Department.id == OrganizationMembership.department_id,
                Department.organization_id == organization_id,
            ),
        )
        statement = statement.group_by(Department.id, Department.name, Expense.currency).order_by(
            Department.name.asc().nullsfirst(), Expense.currency.asc().nullsfirst()
        )
        rows = session.execute(
            statement.where(*_conditions(organization_id, filters, include_date_range=True))
        ).mappings()
        return [
            AnalyticsDepartmentAmount(
                department_id=row["department_id"],
                department_name=row["department_name"],
                **_amount_values(row),
            )
            for row in rows
        ]
    if dimension == "office_location":
        statement = _expense_statement(
            OfficeLocation.id.label("office_location_id"),
            OfficeLocation.name.label("office_location_name"),
            Expense.currency.label("currency"),
            claim_count,
            amount_claim_count,
            amount_total,
        ).outerjoin(
            OfficeLocation,
            and_(
                OfficeLocation.id == OrganizationMembership.office_location_id,
                OfficeLocation.organization_id == organization_id,
            ),
        )
        statement = statement.group_by(
            OfficeLocation.id, OfficeLocation.name, Expense.currency
        ).order_by(OfficeLocation.name.asc().nullsfirst(), Expense.currency.asc().nullsfirst())
        rows = session.execute(
            statement.where(*_conditions(organization_id, filters, include_date_range=True))
        ).mappings()
        return [
            AnalyticsLocationAmount(
                office_location_id=row["office_location_id"],
                office_location_name=row["office_location_name"],
                **_amount_values(row),
            )
            for row in rows
        ]

    statement = _expense_statement(
        Expense.category.label("category"),
        Expense.currency.label("currency"),
        claim_count,
        amount_claim_count,
        amount_total,
    ).where(*_conditions(organization_id, filters, include_date_range=True))
    rows = session.execute(
        statement.group_by(Expense.category, Expense.currency).order_by(
            Expense.category.asc().nullsfirst(), Expense.currency.asc().nullsfirst()
        )
    ).mappings()
    return [
        AnalyticsCategoryAmount(category=row["category"], **_amount_values(row)) for row in rows
    ]


def _monthly_totals(
    session: Session, organization_id: uuid.UUID, filters: AnalyticsFilters
) -> list[AnalyticsMonthlyAmount]:
    month = func.date_trunc("month", Expense.expense_date).cast(Date).label("month")
    claim_count, amount_claim_count, amount_total = _amount_columns()
    statement = _expense_statement(
        month,
        Expense.currency.label("currency"),
        claim_count,
        amount_claim_count,
        amount_total,
    ).where(*_conditions(organization_id, filters, include_date_range=True))
    rows = session.execute(
        statement.group_by(month, Expense.currency).order_by(
            month, Expense.currency.asc().nullsfirst()
        )
    ).mappings()
    return [AnalyticsMonthlyAmount(month=row["month"], **_amount_values(row)) for row in rows]


def overview(
    session: Session, organization_id: uuid.UUID, filters: AnalyticsFilters
) -> AnalyticsOverviewResponse:
    _validate_filters(session, organization_id, filters)
    conditions = _conditions(organization_id, filters, include_date_range=True)
    status_rows = session.execute(
        _expense_statement(Expense.status, func.count(Expense.id))
        .where(*conditions)
        .group_by(Expense.status)
    ).all()
    counts = dict(status_rows)
    status_counts = [
        AnalyticsStatusCount(status=status, claim_count=counts.get(status.value, 0))
        for status in ExpenseStatus
    ]
    total = sum(counts.values())
    requiring_review = counts.get(ExpenseStatus.SUBMITTED.value, 0) + counts.get(
        ExpenseStatus.IN_REVIEW.value, 0
    )

    missing_critical = or_(
        Expense.merchant.is_(None),
        Expense.amount.is_(None),
        Expense.currency.is_(None),
    )
    missing_count = session.execute(
        _expense_statement(func.count(Expense.id)).where(*conditions, missing_critical)
    ).scalar_one()
    uncertain_critical = exists(
        select(ExpenseFieldEvidence.id).where(
            ExpenseFieldEvidence.expense_id == Expense.id,
            ExpenseFieldEvidence.is_current.is_(True),
            ExpenseFieldEvidence.field_name.in_(
                (
                    ExpenseFieldName.MERCHANT.value,
                    ExpenseFieldName.EXPENSE_DATE.value,
                    ExpenseFieldName.AMOUNT.value,
                    ExpenseFieldName.CURRENCY.value,
                )
            ),
            ExpenseFieldEvidence.uncertainty_reason.is_not(None),
        )
    )
    uncertain_count = session.execute(
        _expense_statement(func.count(Expense.id)).where(*conditions, uncertain_critical)
    ).scalar_one()
    unknown_date_count = session.execute(
        _expense_statement(func.count(Expense.id)).where(
            *_conditions(organization_id, filters, include_date_range=False),
            Expense.expense_date.is_(None),
        )
    ).scalar_one()

    return AnalyticsOverviewResponse(
        from_date=filters.from_date,
        to_date=filters.to_date,
        claim_count=total,
        claims_requiring_review=requiring_review,
        claims_needing_information=counts.get(ExpenseStatus.NEEDS_INFO.value, 0),
        claims_missing_critical_fields=missing_count,
        claims_with_uncertain_critical_fields=uncertain_count,
        claims_with_unknown_transaction_date=unknown_date_count,
        status_counts=status_counts,
        status_amounts=_status_amounts(session, organization_id, filters),
        by_department=_overview_breakdown(session, organization_id, filters, "department"),
        by_office_location=_overview_breakdown(
            session, organization_id, filters, "office_location"
        ),
        by_category=_overview_breakdown(session, organization_id, filters, "category"),
        monthly_totals=_monthly_totals(session, organization_id, filters),
    )


def _spend_dimensions(
    group_by: AnalyticsGroupBy, organization_id: uuid.UUID
) -> tuple[list[Any], list[Any], Any]:
    if group_by == AnalyticsGroupBy.MONTH:
        month = func.date_trunc("month", Expense.expense_date).cast(Date).label("bucket_start")
        return [month], [month], None
    if group_by == AnalyticsGroupBy.DEPARTMENT:
        expressions = [
            Department.id.label("department_id"),
            Department.name.label("department_name"),
        ]
        join = and_(
            Department.id == OrganizationMembership.department_id,
            Department.organization_id == organization_id,
        )
        return expressions, [Department.id, Department.name], (Department, join)
    if group_by == AnalyticsGroupBy.LOCATION:
        expressions = [
            OfficeLocation.id.label("office_location_id"),
            OfficeLocation.name.label("office_location_name"),
        ]
        join = and_(
            OfficeLocation.id == OrganizationMembership.office_location_id,
            OfficeLocation.organization_id == organization_id,
        )
        return expressions, [OfficeLocation.id, OfficeLocation.name], (OfficeLocation, join)
    if group_by == AnalyticsGroupBy.CATEGORY:
        category = Expense.category.label("category")
        return [category], [category], None
    if group_by == AnalyticsGroupBy.EMPLOYEE:
        expressions = [
            OrganizationMembership.id.label("employee_membership_id"),
            User.display_name.label("employee_display_name"),
        ]
        return (
            expressions,
            [OrganizationMembership.id, User.display_name],
            (User, User.id == OrganizationMembership.user_id),
        )
    status = Expense.status.label("status")
    return [status], [status], None


def spend(
    session: Session,
    organization_id: uuid.UUID,
    filters: AnalyticsFilters,
    group_by: AnalyticsGroupBy,
    pagination: Pagination,
) -> AnalyticsSpendResponse:
    _validate_filters(session, organization_id, filters)
    selected, grouped, extra_join = _spend_dimensions(group_by, organization_id)
    claim_count, amount_claim_count, amount_total = _amount_columns()
    statement = _expense_statement(
        *selected,
        Expense.currency.label("currency"),
        claim_count,
        amount_claim_count,
        amount_total,
    )
    if extra_join is not None:
        model, condition = extra_join
        statement = statement.outerjoin(model, condition)
    statement = statement.where(
        *_conditions(organization_id, filters, include_date_range=True)
    ).group_by(*grouped, Expense.currency)
    sort_columns = [column.asc().nullsfirst() for column in grouped]
    sort_columns.append(Expense.currency.asc().nullsfirst())
    total_groups = session.execute(
        select(func.count()).select_from(statement.subquery())
    ).scalar_one()
    rows = session.execute(
        statement.order_by(*sort_columns).offset(pagination.offset).limit(pagination.limit)
    ).mappings()
    results = [AnalyticsSpendRow(**dict(row)) for row in rows]

    unknown_date_count = session.execute(
        _expense_statement(func.count(Expense.id)).where(
            *_conditions(organization_id, filters, include_date_range=False),
            Expense.expense_date.is_(None),
        )
    ).scalar_one()
    return AnalyticsSpendResponse(
        from_date=filters.from_date,
        to_date=filters.to_date,
        group_by=group_by,
        claims_with_unknown_transaction_date=unknown_date_count,
        results=build_page(results, pagination, total_groups),
    )


# The result column, per dimension, that carries the bucket's identity. These labels
# are produced by _spend_dimensions, so the key is derived from the very expression
# the group was built from rather than re-read from the descriptor.
_BUCKET_KEY_FIELDS: dict[AnalyticsGroupBy, str] = {
    AnalyticsGroupBy.MONTH: "bucket_start",
    AnalyticsGroupBy.DEPARTMENT: "department_id",
    AnalyticsGroupBy.LOCATION: "office_location_id",
    AnalyticsGroupBy.CATEGORY: "category",
    AnalyticsGroupBy.EMPLOYEE: "employee_membership_id",
    AnalyticsGroupBy.STATUS: "status",
}


def _bucket_key(group_by: AnalyticsGroupBy, row: dict[str, Any]) -> str:
    """Canonical, always-present string key for one dimension's bucket.

    A month is keyed by its ISO start date. Every other dimension is keyed by its
    identifier or value, so a rename cannot silently merge two buckets. A null
    descriptor keeps a stable identity instead of collapsing to an empty string.
    """
    value = row[_BUCKET_KEY_FIELDS[group_by]]
    if value is None:
        return UNASSIGNED_BUCKET_KEY
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def spend_matrix(
    session: Session,
    organization_id: uuid.UUID,
    filters: AnalyticsFilters,
    primary: AnalyticsGroupBy,
    secondary: AnalyticsGroupBy,
    pagination: Pagination,
) -> AnalyticsSpendMatrixResponse:
    """Two-dimensional spend grouped by (primary bucket, secondary bucket, currency).

    The measures, the currency partitioning, the inclusive date range, the undated
    count and the ordering all come from the same helpers ``spend`` uses - the same
    ``_spend_dimensions`` group expressions, ``_amount_columns`` and ``_conditions`` -
    so a matrix cell can only ever be a re-partition of the single-dimension totals,
    never an independently computed number. Grouping by both dimensions and currency
    and summing the result over one dimension reproduces the ``spend`` row exactly.
    """
    if primary == secondary:
        raise ValidationFailed(
            "The primary and secondary dimensions must differ.",
            details=[{"field": "secondary"}],
        )
    _validate_filters(session, organization_id, filters)
    primary_select, primary_group, primary_join = _spend_dimensions(primary, organization_id)
    secondary_select, secondary_group, secondary_join = _spend_dimensions(
        secondary, organization_id
    )
    claim_count, amount_claim_count, amount_total = _amount_columns()
    statement = _expense_statement(
        *primary_select,
        *secondary_select,
        Expense.currency.label("currency"),
        claim_count,
        amount_claim_count,
        amount_total,
    )
    for extra_join in (primary_join, secondary_join):
        if extra_join is not None:
            model, condition = extra_join
            statement = statement.outerjoin(model, condition)
    grouped = [*primary_group, *secondary_group, Expense.currency]
    # Only dated claims are grouped, exactly as in spend: an undated claim is unknown,
    # never a zero bucket in some month.
    statement = statement.where(
        *_conditions(organization_id, filters, include_date_range=True)
    ).group_by(*grouped)
    # Chronological for a month dimension because date_trunc casts to a date; otherwise
    # by the dimension's own key. Deterministic ordering is what makes the opaque cursor
    # meaningful, and it matches spend's sort of the same expressions.
    sort_columns = [column.asc().nullsfirst() for column in primary_group]
    sort_columns.extend(column.asc().nullsfirst() for column in secondary_group)
    sort_columns.append(Expense.currency.asc().nullsfirst())
    total_groups = session.execute(
        select(func.count()).select_from(statement.subquery())
    ).scalar_one()
    rows = session.execute(
        statement.order_by(*sort_columns).offset(pagination.offset).limit(pagination.limit)
    ).mappings()
    results: list[AnalyticsSpendMatrixRow] = []
    for row in rows:
        values = dict(row)
        results.append(
            AnalyticsSpendMatrixRow(
                primary_key=_bucket_key(primary, values),
                secondary_key=_bucket_key(secondary, values),
                **values,
            )
        )

    unknown_date_count = session.execute(
        _expense_statement(func.count(Expense.id)).where(
            *_conditions(organization_id, filters, include_date_range=False),
            Expense.expense_date.is_(None),
        )
    ).scalar_one()
    return AnalyticsSpendMatrixResponse(
        from_date=filters.from_date,
        to_date=filters.to_date,
        primary=primary,
        secondary=secondary,
        claims_with_unknown_transaction_date=unknown_date_count,
        results=build_page(results, pagination, total_groups),
    )


def _share_of_total(part: Decimal | None, whole: Decimal | None) -> str | None:
    """A department's fraction of the organization's expenditure in the same currency.

    Computed with ``Decimal`` (never float) from two figures the database already
    summed, so it is exact to four decimal places. It is a derived display ratio, not
    an authoritative money total, which is why it is safe to derive here at all.
    """
    if part is None or whole is None or whole == 0:
        return None
    return str((Decimal(part) / Decimal(whole)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _department_aggregates() -> list[Any]:
    """Conditional aggregates, defined once so the rows and the totals cannot diverge.

    ``FILTER (WHERE ...)`` keeps every figure in a single pass over the same filtered
    set, which is what makes the department rows a genuine decomposition of the totals
    rather than a second, independently-computed answer.
    """
    approved = Expense.status == ExpenseStatus.APPROVED.value
    return [
        func.count(Expense.id).label("claim_count"),
        func.count(Expense.amount).label("amount_claim_count"),
        func.sum(Expense.amount).label("amount_total"),
        func.count(Expense.id).filter(approved).label("approved_claim_count"),
        func.sum(Expense.amount).filter(approved).label("approved_amount_total"),
        func.count(Expense.id)
        .filter(Expense.status.in_([ExpenseStatus.SUBMITTED.value, ExpenseStatus.IN_REVIEW.value]))
        .label("pending_review_count"),
        func.count(Expense.id)
        .filter(Expense.status == ExpenseStatus.NEEDS_INFO.value)
        .label("needs_info_count"),
        func.count(Expense.id)
        .filter(Expense.status == ExpenseStatus.REJECTED.value)
        .label("rejected_count"),
        func.count(Expense.id)
        .filter(Expense.status == ExpenseStatus.DRAFT.value)
        .label("draft_count"),
        func.count(Expense.id)
        .filter(OrganizationMembership.department_id.is_(None))
        .label("unassigned_claim_count"),
        func.round(func.sum(Expense.amount) / func.nullif(func.count(Expense.amount), 0), 4).label(
            "average_amount_total"
        ),
    ]


def _department_counts(row: Any) -> dict[str, Any]:
    return {
        "approved_claim_count": row["approved_claim_count"],
        "approved_amount_total": row["approved_amount_total"],
        "pending_review_count": row["pending_review_count"],
        "needs_info_count": row["needs_info_count"],
        "rejected_count": row["rejected_count"],
        "draft_count": row["draft_count"],
    }


def department_summary(
    session: Session, organization_id: uuid.UUID, filters: AnalyticsFilters
) -> AnalyticsDepartmentSummaryResponse:
    """Department-wise requested and approved expenditure plus review workload.

    Department membership comes from the member's ``OrganizationMembership`` row - the
    same relationship the rest of the product uses - so a claim's department is a
    persisted employment fact, never a label supplied by a caller. A member with no
    department is reported as an explicit unassigned row rather than dropped or guessed.
    """
    conditions = _conditions(organization_id, filters, include_date_range=True)
    aggregates = _department_aggregates()

    total_statement = _expense_statement(Expense.currency.label("currency"), *aggregates).where(
        *conditions
    )
    total_rows = session.execute(
        total_statement.group_by(Expense.currency).order_by(Expense.currency.asc().nullsfirst())
    ).mappings()

    totals: list[AnalyticsDepartmentTotals] = []
    requested_by_currency: dict[Any, Decimal | None] = {}
    for row in total_rows:
        requested_by_currency[row["currency"]] = row["amount_total"]
        totals.append(
            AnalyticsDepartmentTotals(
                **_amount_values(row),
                **_department_counts(row),
                unassigned_claim_count=row["unassigned_claim_count"],
            )
        )

    department_statement = (
        _expense_statement(
            Department.id.label("department_id"),
            Department.name.label("department_name"),
            Expense.currency.label("currency"),
            *aggregates,
        )
        .outerjoin(
            Department,
            and_(
                Department.id == OrganizationMembership.department_id,
                Department.organization_id == organization_id,
            ),
        )
        .where(*conditions)
        .group_by(Department.id, Department.name, Expense.currency)
        .order_by(
            func.sum(Expense.amount).desc().nullslast(),
            Department.name.asc().nullsfirst(),
            Expense.currency.asc().nullsfirst(),
        )
    )
    departments = [
        AnalyticsDepartmentRow(
            **_amount_values(row),
            **_department_counts(row),
            department_id=row["department_id"],
            department_name=row["department_name"],
            average_amount_total=row["average_amount_total"],
            requested_share=_share_of_total(
                row["amount_total"], requested_by_currency.get(row["currency"])
            ),
        )
        for row in session.execute(department_statement).mappings()
    ]

    unknown_date_count = session.execute(
        _expense_statement(func.count(Expense.id)).where(
            *_conditions(organization_id, filters, include_date_range=False),
            Expense.expense_date.is_(None),
        )
    ).scalar_one()

    return AnalyticsDepartmentSummaryResponse(
        from_date=filters.from_date,
        to_date=filters.to_date,
        claims_with_unknown_transaction_date=unknown_date_count,
        totals=totals,
        departments=departments,
    )
