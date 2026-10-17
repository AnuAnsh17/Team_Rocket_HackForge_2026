"""Authorized claim reads, corrections, submission, review decisions and history."""

from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_actor, get_pagination, get_session
from app.core.enums import ExpenseFieldName, ExpenseStatus, FieldSource, ReviewAction, RoleCode
from app.core.errors import Conflict, Forbidden, NotFound, StaleVersion, ValidationFailed
from app.core.pagination import Pagination, build_page
from app.core.permissions import Permission
from app.core.security import Actor
from app.models.audit import AuditEvent, IdempotencyKey
from app.models.expense import Expense, ExpenseFieldEvidence, LineItem, Trip
from app.models.identity import OrganizationMembership, User
from app.models.receipt import Receipt
from app.models.review import DuplicateCandidate, Finding
from app.schemas.audit import AuditEventListResponse, AuditEventResponse
from app.schemas.common import EvidenceLocation, FieldValue, Money
from app.schemas.expense import (
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseSummary,
    LineItemResponse,
    SubmitExpenseRequest,
    TripSummary,
    UpdateExpenseRequest,
)
from app.schemas.identity import UserSummary
from app.schemas.receipt import ReceiptSummary
from app.schemas.review import DecisionRequest, FindingResponse, ReviewDecisionResponse
from app.services import idempotency_service
from app.services.audit_service import audit_for_actor
from app.services.expense_workflow_service import record_claim_decision, submit_claim
from app.services.scope_service import (
    is_direct_report,
    is_own_claim,
    require_expense_read,
    teammate_membership_ids,
)

router = APIRouter(tags=["expenses"])


def _current_evidence(session: Session, expense_id: uuid.UUID) -> dict[str, ExpenseFieldEvidence]:
    rows = (
        session.execute(
            select(ExpenseFieldEvidence).where(
                ExpenseFieldEvidence.expense_id == expense_id,
                ExpenseFieldEvidence.is_current.is_(True),
            )
        )
        .scalars()
        .all()
    )
    return {row.field_name: row for row in rows}


def _location(row: ExpenseFieldEvidence | None) -> EvidenceLocation | None:
    if row is None or row.receipt_id is None:
        return None
    region = row.region
    normalized = None
    if isinstance(region, dict):
        vals = [region.get(k) for k in ("x", "y", "width", "height")]
        if all(isinstance(v, (int, float)) for v in vals):
            normalized = [float(cast(float, value)) for value in vals]
    return EvidenceLocation(receipt_id=row.receipt_id, page=row.page, region=normalized)


def _field(
    row: ExpenseFieldEvidence | None,
    value: object,
) -> FieldValue[object]:
    if row is None:
        if value is not None:
            raise Conflict("Claim field provenance is unavailable.")
        return FieldValue(value=None, source=None, reviewed=False)
    return FieldValue(
        value=value,
        source=FieldSource(row.source),
        reviewed=row.reviewed,
        confidence=row.confidence,
        evidence=_location(row),
        uncertainty_reason=row.uncertainty_reason,
    )


def expense_detail(session: Session, expense: Expense) -> ExpenseResponse:
    membership = session.get(OrganizationMembership, expense.membership_id)
    user = session.get(User, membership.user_id) if membership else None
    if membership is None or user is None:
        raise Conflict("The claim owner record is unavailable.")
    evidence = _current_evidence(session, expense.id)
    if expense.amount is not None and ExpenseFieldName.AMOUNT.value not in evidence:
        raise Conflict("Claim amount provenance is unavailable.")
    amount_evidence = evidence.get(ExpenseFieldName.AMOUNT.value)
    trip = session.get(Trip, expense.trip_id) if expense.trip_id else None
    receipts = (
        session.execute(
            select(Receipt)
            .where(Receipt.expense_id == expense.id)
            .order_by(Receipt.created_at.asc())
        )
        .scalars()
        .all()
    )
    lines = (
        session.execute(
            select(LineItem)
            .where(LineItem.expense_id == expense.id)
            .order_by(LineItem.line_number.asc())
        )
        .scalars()
        .all()
    )
    findings = (
        session.execute(
            select(Finding)
            .where(Finding.expense_id == expense.id)
            .order_by(Finding.created_at.asc())
        )
        .scalars()
        .all()
    )
    finding_responses = [
        FindingResponse(
            id=row.id,
            expense_id=row.expense_id,
            type=row.finding_type,
            rule_id=row.rule_id,
            policy_version_id=row.policy_version_id,
            result=row.result,
            severity=row.severity,
            message=row.message,
            employee_message=row.employee_message,
            source_reference=row.source_reference,
            evidence=row.evidence,
            calculation=row.calculation,
            expected=row.expected_value,
            observed=row.observed_value,
            recommended_action=row.recommended_action,
            status=row.status,
            expense_version=row.expense_version,
            resolved_at=row.resolved_at,
            superseded_by_finding_id=row.superseded_by_finding_id,
            created_at=row.created_at,
        )
        for row in findings
    ]
    return ExpenseResponse(
        id=expense.id,
        version=expense.version,
        organization_id=expense.organization_id,
        employee=UserSummary(id=user.id, display_name=user.display_name, is_active=user.is_active),
        channel=expense.channel,
        status=expense.status,
        trip_id=expense.trip_id,
        trip=(
            TripSummary(
                id=trip.id,
                purpose=trip.purpose,
                destination_city=trip.destination_city,
                destination_country_code=trip.destination_country_code,
                start_date=trip.start_date,
                end_date=trip.end_date,
                status=trip.status,
            )
            if trip
            else None
        ),
        merchant=_field(evidence.get(ExpenseFieldName.MERCHANT.value), expense.merchant),
        expense_date=_field(
            evidence.get(ExpenseFieldName.EXPENSE_DATE.value), expense.expense_date
        ),
        amount=Money(
            value=expense.amount,
            currency=expense.currency,
            source=FieldSource(amount_evidence.source) if amount_evidence else None,
            reviewed=amount_evidence.reviewed if amount_evidence else False,
            confidence=amount_evidence.confidence if amount_evidence else None,
            evidence=_location(amount_evidence),
            uncertainty_reason=amount_evidence.uncertainty_reason if amount_evidence else None,
        ),
        receipt_number=_field(
            evidence.get(ExpenseFieldName.RECEIPT_NUMBER.value), expense.receipt_number
        ),
        category=expense.category,
        business_purpose=expense.business_purpose,
        client_name=expense.client_name,
        attendee_count=expense.attendee_count,
        amount_reporting=None,
        receipts=[
            ReceiptSummary(
                id=row.id,
                content_url=f"/api/v1/receipts/{row.id}/content",
                extraction_status=row.extraction_status,
                detected_mime_type=row.detected_mime_type,
                byte_size=row.byte_size,
                derivation_type=row.derivation_type,
                uploaded_at=row.created_at,
            )
            for row in receipts
        ],
        line_items=[
            LineItemResponse(
                id=row.id,
                line_number=row.line_number,
                description=row.description,
                quantity=row.quantity,
                unit_amount=row.unit_amount,
                amount=row.amount,
                currency=row.currency,
                tax_amount=row.tax_amount,
                discount_amount=row.discount_amount,
                category=row.category,
                eligibility=row.eligibility,
                ineligibility_reason=row.ineligibility_reason,
            )
            for row in lines
        ],
        findings=finding_responses,
        evaluated_policy_version_id=expense.evaluated_policy_version_id,
        submitted_at=expense.submitted_at,
        decided_at=expense.decided_at,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
    )


def _expense_summary(session: Session, expense: Expense) -> ExpenseSummary:
    membership = session.get(OrganizationMembership, expense.membership_id)
    user = session.get(User, membership.user_id) if membership else None
    if user is None:
        raise Conflict("The claim owner record is unavailable.")
    evidence = _current_evidence(session, expense.id)
    if expense.amount is not None and ExpenseFieldName.AMOUNT.value not in evidence:
        raise Conflict("Claim amount provenance is unavailable.")

    def count(model: Any, *where: Any) -> int:
        return session.execute(select(func.count()).select_from(model).where(*where)).scalar_one()

    return ExpenseSummary(
        id=expense.id,
        version=expense.version,
        employee=UserSummary(id=user.id, display_name=user.display_name, is_active=user.is_active),
        channel=expense.channel,
        status=expense.status,
        merchant=expense.merchant,
        expense_date=expense.expense_date,
        amount=Money(
            value=expense.amount,
            currency=expense.currency,
            source=(
                FieldSource(evidence[ExpenseFieldName.AMOUNT.value].source)
                if ExpenseFieldName.AMOUNT.value in evidence
                else None
            ),
            reviewed=evidence[ExpenseFieldName.AMOUNT.value].reviewed
            if ExpenseFieldName.AMOUNT.value in evidence
            else False,
        ),
        category=expense.category,
        trip_id=expense.trip_id,
        receipt_count=count(Receipt, Receipt.expense_id == expense.id),
        open_finding_count=count(
            Finding, Finding.expense_id == expense.id, Finding.status == "open"
        ),
        blocking_finding_count=count(
            Finding,
            Finding.expense_id == expense.id,
            Finding.status == "open",
            Finding.severity == "blocking",
        ),
        open_duplicate_candidate_count=count(
            DuplicateCandidate,
            DuplicateCandidate.status == "open",
            (DuplicateCandidate.expense_a_id == expense.id)
            | (DuplicateCandidate.expense_b_id == expense.id),
        ),
        submitted_at=expense.submitted_at,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
    )


def _ensure_read_permission(actor: Actor) -> None:
    if not any(
        actor.has(permission)
        for permission in (
            Permission.EXPENSE_READ_OWN,
            Permission.EXPENSE_READ_TEAM,
            Permission.EXPENSE_READ_ORG_SCOPED,
        )
    ):
        raise Forbidden("A claim read permission is required.")


@router.get("/expenses", response_model=ExpenseListResponse, summary="List authorized expenses")
def list_expenses(
    pagination: Pagination = Depends(get_pagination),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> ExpenseListResponse:
    _ensure_read_permission(actor)
    if actor.active_organization_id is None:
        raise Forbidden("An active organization membership is required.")
    memberships: set[uuid.UUID] = set()
    if actor.active_membership_id and actor.has(Permission.EXPENSE_READ_OWN):
        memberships.add(uuid.UUID(actor.active_membership_id))
    if actor.has(Permission.EXPENSE_READ_TEAM):
        memberships.update(teammate_membership_ids(session, actor))
    statement = (
        select(Expense)
        .join(OrganizationMembership, OrganizationMembership.id == Expense.membership_id)
        .where(
            Expense.organization_id == uuid.UUID(actor.active_organization_id),
            OrganizationMembership.organization_id == uuid.UUID(actor.active_organization_id),
        )
    )
    if actor.has(Permission.EXPENSE_READ_ORG_SCOPED):
        pass
    elif memberships:
        statement = statement.where(Expense.membership_id.in_(memberships))
    else:
        return ExpenseListResponse.model_validate(build_page([], pagination, 0))
    total = session.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    rows = (
        session.execute(
            statement.order_by(Expense.created_at.desc(), Expense.id.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        .scalars()
        .all()
    )
    return ExpenseListResponse.model_validate(
        build_page([_expense_summary(session, row) for row in rows], pagination, total)
    )


@router.get(
    "/expenses/{expense_id}", response_model=ExpenseResponse, summary="Read an authorized expense"
)
def get_expense(
    expense_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> ExpenseResponse:
    _ensure_read_permission(actor)
    expense = require_expense_read(session, actor, expense_id)
    return expense_detail(session, expense)


def _lock_expense(session: Session, actor: Actor, expense_id: uuid.UUID) -> Expense:
    expense = session.execute(
        select(Expense).where(Expense.id == expense_id).with_for_update()
    ).scalar_one_or_none()
    if expense is None:
        raise NotFound("That expense was not found.")
    return require_expense_read(session, actor, expense_id)


def _check_version(expense: Expense, expected: int) -> None:
    if expense.version != expected:
        raise StaleVersion()


def _idem(
    session: Session, actor: Actor, request: Request, key: str, payload: object
) -> IdempotencyKey | None:
    return idempotency_service.begin(
        session,
        actor_user_id=uuid.UUID(actor.user_id),
        key=key,
        method=request.method,
        path=request.url.path,
        payload=payload,
    )


@router.patch(
    "/expenses/{expense_id}", response_model=ExpenseResponse, summary="Correct claim fields"
)
def update_expense(
    expense_id: uuid.UUID,
    body: UpdateExpenseRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> ExpenseResponse:
    expense = _lock_expense(session, actor, expense_id)
    owner = is_own_claim(actor, expense)
    if owner:
        actor.require(Permission.EXPENSE_UPDATE_OWN)
        source = FieldSource.EMPLOYEE_INPUT
        reviewer = False
    else:
        actor.require(Permission.EXPENSE_DECIDE_SCOPED)
        source = FieldSource.REVIEWER_CORRECTION
        reviewer = True
    payload = body.model_dump(mode="json")
    idem = _idem(session, actor, request, idempotency_key, payload)
    if idem and idem.response_body:
        return ExpenseResponse.model_validate(idem.response_body)
    _check_version(expense, body.expected_version)
    if owner and expense.status not in (ExpenseStatus.DRAFT.value, ExpenseStatus.NEEDS_INFO.value):
        raise Conflict("Employees may correct only draft or needs-information claims.")
    if not owner and expense.status != ExpenseStatus.IN_REVIEW.value:
        raise Conflict("Scoped reviewers may correct only claims in review.")
    fields = body.model_fields_set - {"expected_version"}
    if not fields:
        raise ValidationFailed("At least one claim field must be supplied.")
    if ("amount" in fields) != ("currency" in fields):
        raise ValidationFailed("Amount and currency must be corrected together.")
    next_amount = body.amount if "amount" in fields else expense.amount
    next_currency = body.currency if "currency" in fields else expense.currency
    if (next_amount is None) != (next_currency is None):
        raise ValidationFailed("Amount and currency must be supplied together.")
    if "trip_id" in fields and body.trip_id is not None:
        trip = session.get(Trip, body.trip_id)
        if (
            trip is None
            or trip.organization_id != expense.organization_id
            or trip.membership_id != expense.membership_id
        ):
            raise ValidationFailed("The trip must belong to this employee and organization.")
    before = {name: getattr(expense, name) for name in fields}
    expense.version += 1
    for name in fields:
        value = getattr(body, name)
        setattr(expense, name, value)
        field_name = ExpenseFieldName.TRIP_ID.value if name == "trip_id" else name
        previous = session.execute(
            select(ExpenseFieldEvidence).where(
                ExpenseFieldEvidence.expense_id == expense.id,
                ExpenseFieldEvidence.field_name == field_name,
                ExpenseFieldEvidence.is_current.is_(True),
            )
        ).scalar_one_or_none()
        if previous:
            previous.is_current = False
        evidence = ExpenseFieldEvidence(
            expense_id=expense.id,
            expense_version=expense.version,
            field_name=field_name,
            source=source.value,
            is_current=True,
            reviewed=reviewer,
            reviewed_by_user_id=uuid.UUID(actor.user_id) if reviewer else None,
            created_by_user_id=uuid.UUID(actor.user_id),
        )
        if name in {"merchant", "category", "business_purpose", "client_name", "currency"}:
            evidence.value_text = str(value) if value is not None else None
        elif name == "expense_date":
            evidence.value_date = value
        elif name == "amount":
            evidence.value_decimal = value
            evidence.currency = next_currency
        elif name == "attendee_count":
            evidence.value_integer = value
        elif name == "trip_id":
            evidence.value_text = str(value) if value is not None else None
        session.add(evidence)
    response = expense_detail(session, expense)
    idempotency_service.complete(idem, status_code=200, body=response.model_dump(mode="json"))
    audit_for_actor(
        session,
        actor,
        action="expense.corrected",
        entity_type="expense",
        entity_id=expense.id,
        before={k: str(v) if v is not None else None for k, v in before.items()},
        after={
            k: str(getattr(expense, k)) if getattr(expense, k) is not None else None for k in fields
        },
    )
    return response


@router.post(
    "/expenses/{expense_id}/submit",
    response_model=ExpenseResponse,
    summary="Submit a complete claim",
)
def submit_expense(
    expense_id: uuid.UUID,
    body: SubmitExpenseRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> ExpenseResponse:
    actor.require(Permission.EXPENSE_SUBMIT_OWN)
    expense = _lock_expense(session, actor, expense_id)
    if not is_own_claim(actor, expense):
        raise NotFound("That expense was not found.")
    idem = _idem(session, actor, request, idempotency_key, body.model_dump(mode="json"))
    if idem and idem.response_body:
        return ExpenseResponse.model_validate(idem.response_body)
    submit_claim(session, actor, expense, body.expected_version)
    response = expense_detail(session, expense)
    idempotency_service.complete(idem, status_code=200, body=response.model_dump(mode="json"))
    return response


@router.post(
    "/expenses/{expense_id}/decisions",
    response_model=ReviewDecisionResponse,
    status_code=201,
    summary="Record a human review decision",
)
def decide_expense(
    expense_id: uuid.UUID,
    body: DecisionRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> ReviewDecisionResponse:
    actor.require(Permission.EXPENSE_DECIDE_SCOPED)
    expense = _lock_expense(session, actor, expense_id)
    if is_own_claim(actor, expense):
        raise Forbidden("Review decisions cannot be made on one's own claim.")
    if (
        RoleCode.MANAGER in actor.roles
        and not (RoleCode.FINANCE_REVIEWER in actor.roles or RoleCode.FINANCE_ADMIN in actor.roles)
        and not is_direct_report(session, actor, expense)
    ):
        raise NotFound("That expense was not found.")
    idem = _idem(session, actor, request, idempotency_key, body.model_dump(mode="json"))
    if idem and idem.response_body:
        return ReviewDecisionResponse.model_validate(idem.response_body)
    manager_scope_used = (
        RoleCode.MANAGER in actor.roles
        and RoleCode.FINANCE_REVIEWER not in actor.roles
        and RoleCode.FINANCE_ADMIN not in actor.roles
    )
    row = record_claim_decision(
        session, actor, expense, body, manager_scope_used=manager_scope_used
    )
    user = session.get(User, uuid.UUID(actor.user_id))
    response = ReviewDecisionResponse(
        id=row.id,
        expense_id=row.expense_id,
        actor_user_id=row.actor_user_id,
        actor_display_name=user.display_name if user else None,
        action=ReviewAction(row.action),
        reason_code=row.reason_code,
        reason=row.reason,
        notes=row.notes,
        previous_status=row.previous_status,
        new_status=row.new_status,
        expense_version=row.expense_version,
        created_at=row.created_at,
    )
    idempotency_service.complete(idem, status_code=201, body=response.model_dump(mode="json"))
    return response


@router.get(
    "/expenses/{expense_id}/audit",
    response_model=AuditEventListResponse,
    summary="Read authorized claim history",
)
def expense_audit(
    expense_id: uuid.UUID,
    pagination: Pagination = Depends(get_pagination),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
) -> AuditEventListResponse:
    _ensure_read_permission(actor)
    expense = require_expense_read(session, actor, expense_id)
    if not is_own_claim(actor, expense) and not any(
        actor.has(p)
        for p in (
            Permission.AUDIT_READ,
            Permission.EXPENSE_READ_TEAM,
            Permission.EXPENSE_READ_ORG_SCOPED,
        )
    ):
        raise Forbidden("Audit history is not available to this actor.")
    statement = select(AuditEvent).where(
        AuditEvent.entity_type == "expense", AuditEvent.entity_id == expense.id
    )
    total = session.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    rows = (
        session.execute(
            statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        .scalars()
        .all()
    )
    return AuditEventListResponse.model_validate(
        build_page([AuditEventResponse.model_validate(row) for row in rows], pagination, total)
    )
