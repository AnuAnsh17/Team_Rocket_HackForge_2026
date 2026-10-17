"""Evaluation scope resolution and the context fingerprint.

The scope is the answer to "which other claims and which context dimension did
this rule look at?". It exists for three reasons:

1. Aggregate rules need the correct set of contributing claims, not a convenient
   one.
2. Re-evaluation needs to know which claims a change invalidates.
3. Idempotency needs a stable key. ``fingerprint`` hashes the resolved dimensions
   together with the contributing claim ids and versions, so re-running
   evaluation for identical inputs produces an identical fingerprint and therefore
   cannot create a second finding.

NULLABLE DIMENSIONS
-------------------
``trip_id`` and the organizational dimensions are nullable. A naive
``GROUP BY trip_id`` over a nullable column produces a NULL group and can
silently double-count, which the build plan explicitly warns about. The
fingerprint therefore records absent dimensions as the literal string
``"<absent>"`` rather than omitting them, so "no trip" is a distinct, explicit
value instead of a missing one.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ExpenseChannel, ExpenseStatus, FieldSource
from app.core.logging import get_logger
from app.models.expense import Expense, ExpenseFieldEvidence, LineItem
from app.models.identity import OrganizationMembership
from app.models.organization import OfficeLocation, Organization
from app.models.receipt import ExtractionRun, Receipt
from app.policy.base import ClaimView, EvaluationScope, FieldSnapshot, RelatedExpense

logger = get_logger(__name__)

ABSENT = "<absent>"

# Claim states that count toward an aggregate. The correct set is a POLICY
# decision and is listed in docs/policy-assumptions.md as an open question, so it
# is expressed as an explicit, overridable constant rather than being buried in a
# query. Until the policy answers it, aggregate rules cannot be activated anyway.
DEFAULT_AGGREGATE_INCLUDED_STATUSES: frozenset[ExpenseStatus] = frozenset(
    {
        ExpenseStatus.SUBMITTED,
        ExpenseStatus.NEEDS_INFO,
        ExpenseStatus.IN_REVIEW,
        ExpenseStatus.APPROVED,
    }
)


def _money_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _date_str(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def compute_fingerprint(
    *,
    expense_id: uuid.UUID,
    expense_version: int,
    policy_version_id: uuid.UUID | None,
    dimensions: dict[str, str | None],
    contributors: tuple[RelatedExpense, ...],
) -> str:
    """Hash the evaluation identity.

    Canonical JSON with sorted keys, so the hash does not depend on dict ordering
    or on Python's set iteration order.
    """
    payload = {
        "expense_id": str(expense_id),
        "expense_version": expense_version,
        "policy_version_id": str(policy_version_id) if policy_version_id else ABSENT,
        "dimensions": {
            key: (value if value is not None else ABSENT) for key, value in dimensions.items()
        },
        "contributors": sorted(
            (
                {
                    "id": str(item.expense_id),
                    "version": item.version,
                    "date": _date_str(item.expense_date),
                    "amount": _money_str(item.amount),
                    "currency": item.currency,
                    "status": item.status.value
                    if isinstance(item.status, ExpenseStatus)
                    else str(item.status),
                }
                for item in contributors
            ),
            key=lambda item: (item["id"], item["version"]),
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _current_field(
    evidence_rows: dict[str, ExpenseFieldEvidence], field_name: str
) -> FieldSnapshot:
    row = evidence_rows.get(field_name)
    if row is None:
        return FieldSnapshot()
    return FieldSnapshot(
        value_text=row.value_text,
        value_decimal=row.value_decimal,
        value_date=row.value_date,
        value_integer=row.value_integer,
        currency=row.currency,
        source=FieldSource(row.source),
        reviewed=row.reviewed,
        confidence=row.confidence,
        uncertainty_reason=row.uncertainty_reason,
    )


def build_claim_view(session: Session, expense: Expense) -> ClaimView:
    """Assemble the read-only claim snapshot the evaluator works from.

    Values come from the field-evidence rows, not from the denormalised columns on
    ``expenses``, because only the evidence rows carry provenance. This is what
    prevents employee-entered text from being treated as receipt evidence.
    """
    evidence_rows: dict[str, ExpenseFieldEvidence] = {
        row.field_name: row
        for row in session.execute(
            select(ExpenseFieldEvidence).where(
                ExpenseFieldEvidence.expense_id == expense.id,
                ExpenseFieldEvidence.is_current.is_(True),
            )
        ).scalars()
    }

    receipt_count = (
        session.execute(select(Receipt.id).where(Receipt.expense_id == expense.id)).scalars().all()
    )

    failed_extraction = bool(
        session.execute(
            select(ExtractionRun.id)
            .join(Receipt, ExtractionRun.receipt_id == Receipt.id)
            .where(Receipt.expense_id == expense.id, ExtractionRun.status == "failed")
        )
        .scalars()
        .all()
    )

    line_item_count = len(
        session.execute(select(LineItem.id).where(LineItem.expense_id == expense.id))
        .scalars()
        .all()
    )

    amount_snapshot = _current_field(evidence_rows, "amount")
    if amount_snapshot.value_decimal is None and expense.amount is not None:
        # Fall back to the stored column only to report the observed value; the
        # snapshot remains not-usable because it has no provenance row.
        amount_snapshot = FieldSnapshot(
            value_decimal=expense.amount,
            currency=expense.currency,
            source=amount_snapshot.source,
            reviewed=amount_snapshot.reviewed,
            uncertainty_reason=amount_snapshot.uncertainty_reason,
        )

    return ClaimView(
        expense_id=expense.id,
        version=expense.version,
        status=ExpenseStatus(expense.status),
        channel=ExpenseChannel(expense.channel),
        merchant=_current_field(evidence_rows, "merchant"),
        expense_date=_current_field(evidence_rows, "expense_date"),
        amount=amount_snapshot,
        currency=expense.currency or _current_field(evidence_rows, "currency").value_text,
        category=expense.category,
        business_purpose=expense.business_purpose,
        client_name=expense.client_name,
        attendee_count=expense.attendee_count,
        line_item_count=line_item_count,
        receipt_count=len(receipt_count),
        has_failed_extraction=failed_extraction,
    )


def gather_related_expenses(
    session: Session,
    *,
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    period_start: date | None,
    period_end: date | None,
    included_statuses: frozenset[ExpenseStatus] = DEFAULT_AGGREGATE_INCLUDED_STATUSES,
) -> tuple[RelatedExpense, ...]:
    """Claims inside one aggregate scope.

    When the period is unknown the result is empty and the caller must record an
    unresolved reason. Returning every claim in the organization instead would
    produce a confidently wrong aggregate.
    """
    if period_start is None or period_end is None:
        return ()

    rows = (
        session.execute(
            select(Expense).where(
                Expense.organization_id == organization_id,
                Expense.membership_id == membership_id,
                Expense.expense_date.is_not(None),
                Expense.expense_date >= period_start,
                Expense.expense_date <= period_end,
                Expense.status.in_([status.value for status in included_statuses]),
            )
        )
        .scalars()
        .all()
    )

    return tuple(
        RelatedExpense(
            expense_id=row.id,
            version=row.version,
            expense_date=row.expense_date,
            amount=row.amount,
            currency=row.currency,
            status=ExpenseStatus(row.status),
            category=row.category,
            trip_id=row.trip_id,
            office_location_id=None,
        )
        for row in rows
    )


def resolve_scope(
    session: Session,
    expense: Expense,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    policy_version_id: uuid.UUID | None = None,
) -> EvaluationScope:
    """Resolve every context dimension and compute the fingerprint."""
    from app.models.expense import Trip

    membership = session.get(OrganizationMembership, expense.membership_id)
    unresolved: list[str] = []
    if membership is None:
        unresolved.append("the claim's organization membership could not be resolved")

    organization = session.get(Organization, expense.organization_id)
    timezone = organization.timezone if organization else None
    if timezone is None:
        unresolved.append(
            "the organization's timezone is not configured, so a day boundary cannot be "
            "established for period-based rules"
        )
    jurisdiction = organization.jurisdiction_code if organization else None
    legal_entity = organization.legal_entity_name if organization else None
    if organization is not None and not jurisdiction:
        # Recorded as an unresolved reason rather than defaulted: a claim whose
        # jurisdiction is unknown cannot be matched against a jurisdiction-scoped
        # assignment, and guessing one would silently change which policy applies.
        unresolved.append(
            "the organization's jurisdiction is not recorded, so jurisdiction-scoped policy "
            "assignments cannot be evaluated"
        )

    office_location_id: uuid.UUID | None = None
    if membership is not None:
        office_location_id = membership.office_location_id
        if office_location_id is not None:
            location = session.get(OfficeLocation, office_location_id)
            if location is not None and location.timezone:
                timezone = location.timezone

    trip = session.get(Trip, expense.trip_id) if expense.trip_id else None

    dimensions: dict[str, str | None] = {
        "organization": str(expense.organization_id),
        "office_location": str(office_location_id) if office_location_id else None,
        "department": str(membership.department_id)
        if membership and membership.department_id
        else None,
        "cost_center": str(membership.cost_center_id)
        if membership and membership.cost_center_id
        else None,
        "job_grade": str(membership.job_grade_id)
        if membership and membership.job_grade_id
        else None,
        "jurisdiction": jurisdiction,
        "legal_entity": legal_entity,
        "category": expense.category,
        "trip": str(expense.trip_id) if expense.trip_id else None,
        "expense_date": _date_str(expense.expense_date),
        "timezone": timezone,
    }

    related: tuple[RelatedExpense, ...] = ()
    if period_start is not None and period_end is not None:
        related = gather_related_expenses(
            session,
            organization_id=expense.organization_id,
            membership_id=expense.membership_id,
            period_start=period_start,
            period_end=period_end,
        )
    else:
        unresolved.append("no policy period has been resolved, so no aggregate scope was gathered")

    fingerprint = compute_fingerprint(
        expense_id=expense.id,
        expense_version=expense.version,
        policy_version_id=policy_version_id,
        dimensions=dimensions,
        contributors=related,
    )

    return EvaluationScope(
        organization_id=expense.organization_id,
        membership_id=expense.membership_id,
        office_location_id=office_location_id,
        department_id=membership.department_id if membership else None,
        cost_center_id=membership.cost_center_id if membership else None,
        job_grade_id=membership.job_grade_id if membership else None,
        jurisdiction_code=jurisdiction,
        legal_entity_name=legal_entity,
        timezone=timezone,
        trip_id=expense.trip_id,
        trip_destination_city=trip.destination_city if trip else None,
        category=expense.category,
        period_start=period_start,
        period_end=period_end,
        related_expenses=related,
        fingerprint=fingerprint,
        unresolved_reasons=tuple(unresolved),
        dimensions=dimensions,
    )
