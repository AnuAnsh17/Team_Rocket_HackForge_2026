"""Synthetic demo dataset.

Every record this module creates is fictional, and every identifier is derived
deterministically with ``uuid5`` from a fixed namespace so that seeding is
repeatable and reset is precise.

What the seed deliberately does NOT create, and why:

* **No job grades.** Grade levels and bands are organizational data. Inventing a
  ladder here would silently create the "higher grade means higher allowance"
  assumption that docs/role-policy-hierarchy.md forbids.
* **No allowance limits.** An allowance amount without a cited clause cannot be
  stored at all (``allowance_profile_items.limit_requires_source``).
* **No active policy rules.** A rule cannot be activated without a verified clause
  and a named validator (``policy_rules.source_requires_validation``). The seeded
  policy version is left in the DRAFT state on purpose, so the demo shows the real
  current behaviour: every claim evaluates to UNKNOWN because no policy governs it.
* Synthetic claim scenarios are kept separate from real policy data. They are
  created through the same workflow functions as user claims and never contain
  fabricated extraction results.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import (
    ApprovalState,
    AuditActorType,
    DerivationType,
    ExpenseStatus,
    ExtractionStatus,
    MembershipStatus,
    PolicyReviewState,
    ReviewAction,
    RoleCode,
    StorageBackend,
)
from app.core.errors import Conflict
from app.core.logging import get_logger
from app.core.permissions import Permission
from app.core.security import Identity
from app.models.expense import Expense
from app.models.identity import OrganizationMembership, ReportingRelationship, RoleAssignment, User
from app.models.organization import (
    CostCenter,
    Department,
    OfficeLocation,
    Organization,
)
from app.models.policy import PolicyAssignment, PolicyDocument, PolicyRule, PolicyVersion
from app.models.receipt import ExtractionRun, Receipt
from app.schemas.demo import DemoResetResponse, DemoSeedResponse
from app.schemas.expense import CreateExpenseRequest
from app.schemas.review import DecisionRequest
from app.services.actor_service import resolve_actor
from app.services.audit_service import audit
from app.services.expense_workflow_service import (
    create_draft_claim,
    record_claim_decision,
    submit_claim,
)
from app.services.scope_service import require_expense_read
from app.storage.base import ReceiptStorage, validate_upload
from app.storage.factory import build_receipt_storage

logger = get_logger(__name__)

DEMO_DATASET = "proofline-synthetic-v1"
_NAMESPACE = uuid.UUID("6f6c7a2e-0001-4000-8000-000000000001")
DEMO_ORG_SLUG = "demo-holdings"
DEMO_ORG_NAME = "Demo Holdings (synthetic)"


def _sid(name: str) -> uuid.UUID:
    """Deterministic identifier for a synthetic record."""
    return uuid.uuid5(_NAMESPACE, name)


@dataclass(frozen=True, slots=True)
class DemoPerson:
    key: str
    display_name: str
    roles: tuple[RoleCode, ...]


# Fictional people only. No real name, email or employee code appears here.
DEMO_PEOPLE: tuple[DemoPerson, ...] = (
    DemoPerson("employee.asha", "Asha Menon (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson("employee.rohit", "Rohit Verma (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson("employee.nisha", "Nisha Kapoor (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson("employee.vikram", "Vikram Das (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson("employee.leela", "Leela Sen (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson("employee.kiran", "Kiran Rao (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson("employee.amir", "Amir Khan (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson("employee.tara", "Tara Bose (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson("employee.dev", "Devika Iyer (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson("employee.omar", "Omar Sen (synthetic employee)", (RoleCode.EMPLOYEE,)),
    DemoPerson(
        "manager.priya",
        "Priya Nair (synthetic manager)",
        (RoleCode.EMPLOYEE, RoleCode.MANAGER),
    ),
    DemoPerson(
        "finance.reviewer",
        "Kabir Shah (synthetic finance reviewer)",
        (RoleCode.EMPLOYEE, RoleCode.FINANCE_REVIEWER),
    ),
    DemoPerson(
        "finance.admin",
        "Meera Iyer (synthetic finance administrator)",
        (RoleCode.EMPLOYEE, RoleCode.FINANCE_ADMIN),
    ),
    DemoPerson(
        "hr.reviewer",
        "Sana Qureshi (synthetic HR reviewer)",
        (RoleCode.EMPLOYEE, RoleCode.HR_REVIEWER),
    ),
    DemoPerson(
        "org.admin",
        "Dev Anand (synthetic organization administrator)",
        (RoleCode.EMPLOYEE, RoleCode.ORG_ADMIN),
    ),
    DemoPerson(
        "policy.admin",
        "Ira Bose (synthetic policy administrator)",
        (RoleCode.EMPLOYEE, RoleCode.POLICY_ADMIN),
    ),
    DemoPerson("auditor", "Nikhil Rao (synthetic auditor)", (RoleCode.AUDITOR,)),
)


@dataclass
class _SeedState:
    users: list[uuid.UUID] = field(default_factory=list)
    memberships: list[uuid.UUID] = field(default_factory=list)


def demo_identity_subject(person_key: str) -> str:
    """The X-Demo-Actor-Id value for a seeded person."""
    return str(_sid(f"user:{person_key}"))


def seed_demo_dataset(
    session: Session,
    *,
    actor_user_id: uuid.UUID | None = None,
    actor_label: str | None = "demo seed",
    include_claim_scenarios: bool = False,
    storage: ReceiptStorage | None = None,
    rollback_callbacks: list[Callable[[], None]] | None = None,
) -> DemoSeedResponse:
    """Load the deterministic synthetic dataset. Idempotent per record.

    Existing rows with the same derived identifiers are reused rather than
    duplicated, so calling this twice does not create two demo organizations.
    """
    state = _SeedState()
    organization = _ensure_organization(session)
    departments = _ensure_structure(session, organization.id)
    _ensure_people(session, organization.id, departments, state)
    policy_version = _ensure_draft_policy(session, organization.id)
    synthetic_rules = (
        _ensure_synthetic_policy(session, organization.id)
        if settings.demo_synthetic_policy_enabled
        else 0
    )
    claim_scenarios = 0
    if include_claim_scenarios:
        storage = storage or build_receipt_storage(settings)
        claim_scenarios = _ensure_claim_scenarios(
            session, organization.id, storage, rollback_callbacks=rollback_callbacks
        )

    audit(
        session,
        action="demo.seed",
        entity_type="organization",
        entity_id=organization.id,
        actor_type=AuditActorType.DEMO,
        organization_id=organization.id,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        after={
            "dataset": DEMO_DATASET,
            "policy_version_state": policy_version.review_state,
            "synthetic_policy_enabled": settings.demo_synthetic_policy_enabled,
            "synthetic_policy_rules": synthetic_rules,
            "synthetic_claim_scenarios": claim_scenarios,
        },
    )

    return DemoSeedResponse(
        dataset=DEMO_DATASET,
        organizations=1,
        users=len(state.users),
        memberships=len(state.memberships),
        claim_scenarios_seeded=claim_scenarios,
        policy_rules_activated=synthetic_rules,
        notes=[
            "All names, organizations and identifiers are fictional and deterministic.",
            "No job grades or allowance limits were created; those require real organizational data and policy clauses.",
            "The seeded policy version is intentionally left in draft state, so every claim "
            "currently evaluates to UNKNOWN rather than PASS.",
            *(
                [
                    "A separate fictional demo policy is enabled. Its meal cap is invented for "
                    "mechanics-only demonstrations and is never an authoritative company rule."
                ]
                if synthetic_rules
                else ["DEMO_SYNTHETIC_POLICY_ENABLED is false; no fictional policy rule is active."]
            ),
            "Use the identifiers below as X-Demo-Actor-Id values in demo mode.",
            *(
                [
                    f"{claim_scenarios} deterministic synthetic claim scenarios were seeded through the shared claim workflow services."
                ]
                if include_claim_scenarios
                else []
            ),
            *[f"{person.key} -> {demo_identity_subject(person.key)}" for person in DEMO_PEOPLE],
        ],
    )


def reset_demo_dataset(
    session: Session,
    *,
    actor_label: str | None = "demo reset",
) -> DemoResetResponse:
    """Remove only the records this module created.

    Scoped to the fixed demo organization and to users whose auth_provider is
    'demo', so a reset can never touch non-demo data.
    """
    organization = session.execute(
        select(Organization).where(Organization.slug == DEMO_ORG_SLUG)
    ).scalar_one_or_none()

    demo_user_ids: set[uuid.UUID] = set()
    organizations_removed = 0
    if organization is not None:
        demo_user_ids = set(
            session.execute(
                select(OrganizationMembership.user_id).where(
                    OrganizationMembership.organization_id == organization.id
                )
            )
            .scalars()
            .all()
        )
        audit(
            session,
            action="demo.reset",
            entity_type="organization",
            entity_id=organization.id,
            actor_type=AuditActorType.DEMO,
            organization_id=None,
            actor_label=actor_label,
            before={"slug": organization.slug, "dataset": DEMO_DATASET},
        )
        session.delete(organization)
        session.flush()
        organizations_removed = 1

    # Remove only synthetic identities that belonged to this dataset and have
    # no remaining memberships. Demo identities in any other organization are
    # outside the reset's authority.
    users_removed = 0
    for user_id in demo_user_ids:
        user = session.get(User, user_id)
        if user is None or user.auth_provider != "demo":
            continue
        has_other_membership = session.execute(
            select(OrganizationMembership.id)
            .where(OrganizationMembership.user_id == user_id)
            .limit(1)
        ).first()
        if has_other_membership is None:
            session.delete(user)
            users_removed += 1

    return DemoResetResponse(
        dataset=DEMO_DATASET,
        organizations_removed=organizations_removed,
        users_removed=users_removed,
        notes=[
            "Only the synthetic demo organization and its demo-provider users without other memberships were removed.",
            "Audit events are append-only and intentionally survive a reset; the reset itself "
            "is recorded as an audit event.",
        ],
    )


def demo_receipt_object_keys(session: Session) -> tuple[str, ...]:
    """Return private object keys belonging to this dataset for post-commit cleanup."""
    return tuple(
        session.execute(
            select(Receipt.object_key)
            .join(Expense, Expense.id == Receipt.expense_id)
            .join(Organization, Organization.id == Expense.organization_id)
            .where(Organization.slug == DEMO_ORG_SLUG)
        )
        .scalars()
        .all()
    )


_DEMO_RECEIPT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c63f8ffffff7f0009fb03fd2a86e38a0000000049454e44ae426082"
)


def _ensure_claim_scenarios(
    session: Session,
    organization_id: uuid.UUID,
    storage: ReceiptStorage,
    *,
    rollback_callbacks: list[Callable[[], None]] | None = None,
) -> int:
    """Seed deterministic claims through the shared claim workflow services."""
    scenarios = (
        ("draft", "employee.asha", None),
        ("submitted", "employee.rohit", None),
        ("in_review", "employee.nisha", ReviewAction.ESCALATE),
        ("needs_info", "employee.vikram", ReviewAction.REQUEST_CORRECTION),
        ("approved", "employee.leela", ReviewAction.APPROVE),
        ("rejected", "employee.kiran", ReviewAction.REJECT),
    )
    finance_actor = resolve_actor(
        session, Identity(subject=demo_identity_subject("finance.reviewer"), provider="demo")
    )
    finance_actor.require(Permission.EXPENSE_DECIDE_SCOPED)

    for index, (state, person_key, action) in enumerate(scenarios):
        employee_actor = resolve_actor(
            session, Identity(subject=demo_identity_subject(person_key), provider="demo")
        )
        employee_actor.require(Permission.EXPENSE_CREATE_OWN)
        expense_id = _sid(f"expense:claim-lifecycle:{state}")
        expense = session.get(Expense, expense_id)
        if expense is None:
            body = CreateExpenseRequest(
                channel="web",
                merchant=f"Synthetic Demo Merchant {index + 1}",
                expense_date=date(2026, 10, index + 1),
                amount=Decimal("1250.00"),
                currency="INR",
                category="meal",
                business_purpose="Fictional demonstration claim; no reimbursement rule implied.",
            )
            expense = create_draft_claim(session, employee_actor, body, expense_id=expense_id)
        if state == "draft":
            continue

        receipt_id = _sid(f"receipt:claim-lifecycle:{state}")
        if session.get(Receipt, receipt_id) is None:
            checked = validate_upload(
                _DEMO_RECEIPT_PNG,
                declared_mime_type="image/png",
                max_bytes=settings.receipt_max_upload_bytes,
            )
            if not checked.accepted or checked.detected_mime_type is None:
                raise Conflict("The synthetic demo receipt did not pass upload validation.")
            stored = storage.save(
                organization_id=organization_id,
                expense_id=expense.id,
                data=_DEMO_RECEIPT_PNG,
                content_type=checked.detected_mime_type,
            )
            if rollback_callbacks is not None:

                def cleanup_object(object_key: str = stored.object_key) -> None:
                    try:
                        storage.delete(object_key)
                    except Exception:
                        logger.error("could not clean up a synthetic receipt after seed rollback")

                rollback_callbacks.append(cleanup_object)
            receipt = Receipt(
                id=receipt_id,
                organization_id=organization_id,
                expense_id=expense.id,
                storage_backend=StorageBackend(stored.storage_backend).value,
                object_key=stored.object_key,
                original_filename=f"synthetic-demo-{state}.png",
                detected_mime_type=checked.detected_mime_type,
                declared_mime_type="image/png",
                byte_size=stored.byte_size,
                sha256=stored.sha256,
                derivation_type=DerivationType.ORIGINAL.value,
                extraction_status=ExtractionStatus.PENDING.value,
                uploaded_by_user_id=uuid.UUID(employee_actor.user_id),
            )
            try:
                session.add(receipt)
                session.flush()
                session.add(
                    ExtractionRun(
                        id=_sid(f"extraction-run:claim-lifecycle:{state}"),
                        receipt_id=receipt.id,
                        provider="pending",
                        status=ExtractionStatus.PENDING.value,
                        attempt_count=0,
                        created_by_user_id=uuid.UUID(employee_actor.user_id),
                    )
                )
                session.flush()
                audit(
                    session,
                    action="receipt.demo_seeded",
                    entity_type="receipt",
                    entity_id=receipt.id,
                    actor_type=AuditActorType.DEMO,
                    organization_id=organization_id,
                    actor_user_id=uuid.UUID(employee_actor.user_id),
                    actor_label=f"{person_key} (synthetic)",
                    after={
                        "expense_id": str(expense.id),
                        "status": "pending",
                        "synthetic": True,
                    },
                )
            except Exception:
                if rollback_callbacks is None:
                    try:
                        storage.delete(stored.object_key)
                    except Exception:
                        logger.error("could not clean up a synthetic receipt after seed failure")
                raise

        if expense.status == ExpenseStatus.DRAFT.value:
            submit_claim(session, employee_actor, expense, expense.version)
        if action is not None and expense.status == ExpenseStatus.SUBMITTED.value:
            require_expense_read(session, finance_actor, expense.id)
            reason = (
                "Synthetic demo correction request: please confirm the fictional attendee context."
                if action == ReviewAction.REQUEST_CORRECTION
                else "Synthetic demonstration decision; not a policy outcome."
                if action == ReviewAction.REJECT
                else None
            )
            record_claim_decision(
                session,
                finance_actor,
                expense,
                DecisionRequest(action=action, reason=reason, expected_version=expense.version),
            )
    session.flush()
    return len(scenarios)


def _ensure_organization(session: Session) -> Organization:
    organization = session.execute(
        select(Organization).where(Organization.slug == DEMO_ORG_SLUG)
    ).scalar_one_or_none()
    if organization is not None:
        return organization
    organization = Organization(
        id=_sid("organization"),
        name=DEMO_ORG_NAME,
        slug=DEMO_ORG_SLUG,
        legal_entity_name="Demo Holdings Private Limited (synthetic)",
        jurisdiction_code="IN",
        # Left unset on purpose: the real operating timezone is an unresolved
        # policy question and defaulting it would invent a day-boundary rule.
        timezone=None,
        reporting_currency=None,
        is_demo=True,
    )
    session.add(organization)
    session.flush()
    return organization


def _ensure_structure(session: Session, organization_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Create departments, cost centers and office locations."""
    created: dict[str, uuid.UUID] = {}
    for key, code, name in (
        ("engineering", "ENG", "Engineering (synthetic)"),
        ("sales", "SLS", "Sales (synthetic)"),
        ("finance", "FIN", "Finance (synthetic)"),
        ("operations", "OPS", "Operations (synthetic)"),
        ("people", "PPL", "People (synthetic)"),
        ("product", "PRD", "Product (synthetic)"),
    ):
        existing = session.execute(
            select(Department).where(
                Department.organization_id == organization_id, Department.code == code
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Department(
                id=_sid(f"department:{key}"),
                organization_id=organization_id,
                code=code,
                name=name,
            )
            session.add(existing)
            session.flush()
        created[f"department:{key}"] = existing.id

    for key, code, name in (
        ("cc-eng", "CC-ENG", "Engineering cost center (synthetic)"),
        ("cc-sales", "CC-SLS", "Sales cost center (synthetic)"),
    ):
        existing_cc = session.execute(
            select(CostCenter).where(
                CostCenter.organization_id == organization_id, CostCenter.code == code
            )
        ).scalar_one_or_none()
        if existing_cc is None:
            existing_cc = CostCenter(
                id=_sid(f"cost_center:{key}"),
                organization_id=organization_id,
                code=code,
                name=name,
            )
            session.add(existing_cc)
            session.flush()
        created[f"cost_center:{key}"] = existing_cc.id

    for key, code, name, city, country in (
        ("blr", "BLR", "Bengaluru office (synthetic)", "Bengaluru", "IN"),
        ("mum", "MUM", "Mumbai office (synthetic)", "Mumbai", "IN"),
    ):
        existing_office = session.execute(
            select(OfficeLocation).where(
                OfficeLocation.organization_id == organization_id, OfficeLocation.code == code
            )
        ).scalar_one_or_none()
        if existing_office is None:
            existing_office = OfficeLocation(
                id=_sid(f"office:{key}"),
                organization_id=organization_id,
                code=code,
                name=name,
                city=city,
                country_code=country,
            )
            session.add(existing_office)
            session.flush()
        created[f"office:{key}"] = existing_office.id

    return created


def _ensure_people(
    session: Session,
    organization_id: uuid.UUID,
    structure: dict[str, uuid.UUID],
    state: _SeedState,
) -> None:
    """Create synthetic users, memberships, role grants and reporting edges."""
    placement: dict[str, tuple[str, str]] = {
        "employee.asha": ("department:engineering", "office:blr"),
        "employee.rohit": ("department:sales", "office:mum"),
        "employee.nisha": ("department:engineering", "office:blr"),
        "employee.vikram": ("department:sales", "office:mum"),
        "employee.leela": ("department:operations", "office:blr"),
        "employee.kiran": ("department:operations", "office:mum"),
        "employee.amir": ("department:people", "office:blr"),
        "employee.tara": ("department:product", "office:mum"),
        "employee.dev": ("department:product", "office:blr"),
        "employee.omar": ("department:people", "office:mum"),
        "manager.priya": ("department:engineering", "office:blr"),
        "finance.reviewer": ("department:finance", "office:blr"),
        "finance.admin": ("department:finance", "office:blr"),
        "hr.reviewer": ("department:finance", "office:mum"),
        "org.admin": ("department:finance", "office:blr"),
        "policy.admin": ("department:finance", "office:blr"),
        "auditor": ("department:finance", "office:blr"),
    }
    primary_manager: dict[str, str] = {
        "employee.asha": "manager.priya",
        "employee.rohit": "manager.priya",
        "employee.nisha": "manager.priya",
        "employee.vikram": "manager.priya",
        "employee.leela": "manager.priya",
        "employee.kiran": "manager.priya",
        "employee.amir": "manager.priya",
        "employee.tara": "manager.priya",
        "employee.dev": "manager.priya",
        "employee.omar": "manager.priya",
    }

    membership_ids: dict[str, uuid.UUID] = {}

    for person in DEMO_PEOPLE:
        department_key, office_key = placement[person.key]
        user = session.get(User, _sid(f"user:{person.key}"))
        if user is None:
            user = User(
                id=_sid(f"user:{person.key}"),
                display_name=person.display_name,
                email=None,
                auth_provider="demo",
                external_subject=str(_sid(f"user:{person.key}")),
                is_active=True,
                primary_organization_id=organization_id,
            )
            session.add(user)
            session.flush()
        state.users.append(user.id)

        membership = session.get(OrganizationMembership, _sid(f"membership:{person.key}"))
        if membership is None:
            membership = OrganizationMembership(
                id=_sid(f"membership:{person.key}"),
                organization_id=organization_id,
                user_id=user.id,
                employee_code=f"DEMO-{person.key.upper().replace('.', '-')}",
                status=MembershipStatus.ACTIVE.value,
                # job_grade_id is left unset: grade levels are organizational data
                # and inventing them would create an allowance assumption.
                job_grade_id=None,
                department_id=structure[department_key],
                cost_center_id=(
                    structure.get("cost_center:cc-sales")
                    if department_key == "department:sales"
                    else structure.get("cost_center:cc-eng")
                    if department_key == "department:engineering"
                    else None
                ),
                office_location_id=structure[office_key],
                joined_on=None,
                is_primary=person.key == "employee.asha",
            )
            session.add(membership)
            session.flush()
        state.memberships.append(membership.id)
        membership_ids[person.key] = membership.id

        for role in person.roles:
            existing_grant = session.execute(
                select(RoleAssignment).where(
                    RoleAssignment.membership_id == membership.id,
                    RoleAssignment.role == role.value,
                    RoleAssignment.scope_type == "organization",
                    RoleAssignment.scope_id == organization_id,
                )
            ).scalar_one_or_none()
            if existing_grant is None:
                session.add(
                    RoleAssignment(
                        id=_sid(f"role:{person.key}:{role.value}"),
                        organization_id=organization_id,
                        membership_id=membership.id,
                        role=role.value,
                        scope_type="organization",
                        # Always populated; equals the organization id for
                        # organization scope so the uniqueness constraint holds.
                        scope_id=organization_id,
                        granted_at=None,
                        reason="synthetic demo seed",
                    )
                )

    for employee_key, manager_key in primary_manager.items():
        existing_edge = session.execute(
            select(ReportingRelationship).where(
                ReportingRelationship.employee_membership_id == membership_ids[employee_key],
                ReportingRelationship.manager_membership_id == membership_ids[manager_key],
            )
        ).scalar_one_or_none()
        if existing_edge is None:
            session.add(
                ReportingRelationship(
                    id=_sid(f"reporting:{employee_key}:{manager_key}"),
                    organization_id=organization_id,
                    employee_membership_id=membership_ids[employee_key],
                    manager_membership_id=membership_ids[manager_key],
                    relationship_type="primary",
                    # A fixed historical start date keeps the edge deterministic
                    # without depending on the wall clock.
                    effective_from=date(2020, 1, 1),
                    effective_to=None,
                )
            )

    session.flush()


def _ensure_draft_policy(session: Session, organization_id: uuid.UUID) -> PolicyVersion:
    """Create a synthetic DRAFT policy version containing zero rules.

    Left in draft state deliberately. The demo therefore shows the true current
    behaviour - every claim evaluates to UNKNOWN - instead of a fabricated
    compliant result.
    """
    document = session.get(PolicyDocument, _sid("policy-document"))
    if document is None:
        document = PolicyDocument(
            id=_sid("policy-document"),
            organization_id=organization_id,
            title="Synthetic demo policy placeholder - NOT the approved company policy",
            source_file_name=None,
            source_file_sha256=None,
            authoritative=False,
            notes=(
                "Created by the demo seed so the policy surfaces are exercised. This document "
                "is not a real policy and carries no clauses."
            ),
        )
        session.add(document)
        session.flush()

    version = session.get(PolicyVersion, _sid("policy-version"))
    if version is None:
        version = PolicyVersion(
            id=_sid("policy-version"),
            policy_document_id=document.id,
            version_label="demo-draft-0",
            effective_from=None,
            effective_to=None,
            review_state=PolicyReviewState.DRAFT.value,
            notes=(
                "Deliberately unapproved and empty. No rule can be activated without a verified "
                "source clause and a named validator."
            ),
        )
        session.add(version)
        session.flush()
    return version


DEMO_POLICY_NATURE = "DEMO ONLY - FICTIONAL"
DEMO_POLICY_VERSION_LABEL = "DEMO ONLY - fictional v2 (category ceilings)"
DEMO_POLICY_DOCUMENT_TITLE = (
    f"{DEMO_POLICY_NATURE}: fictional company expense policy (not company policy)"
)

# Fictional per-claim ceilings for the demo policy. This is DATA, not logic: it is written
# into validated rule parameters and mirrored in docs/demo-company-expense-policy.md. No
# amount appears anywhere under app/policy/, so the engine cannot acquire a hard-coded
# threshold. Categories without an entry here are deliberately uncovered, and the evaluator
# reports UNKNOWN for them rather than PASS.
DEMO_POLICY_CLAUSES: tuple[tuple[str, str, str], ...] = (
    ("DEMO-EXP-001", "meal", "1500.00"),
    ("DEMO-EXP-002", "accommodation", "8000.00"),  # per claim, explicitly not per night
    ("DEMO-EXP-003", "ground_transport", "2500.00"),
    ("DEMO-EXP-004", "fuel", "6000.00"),
    ("DEMO-EXP-005", "office_supplies", "10000.00"),
    ("DEMO-EXP-006", "air_travel", "25000.00"),
    ("DEMO-EXP-007", "rail_bus", "12000.00"),
    ("DEMO-EXP-008", "parking", "1200.00"),
    ("DEMO-EXP-009", "conference", "20000.00"),
    ("DEMO-EXP-010", "telecom", "3000.00"),
)


def _ensure_synthetic_policy(session: Session, organization_id: uuid.UUID) -> int:
    """Seed the fictional demo policy at its current version; return the active rule count.

    Only reached when DEMO_SYNTHETIC_POLICY_ENABLED is true in a local environment; the
    caller guards that. Idempotent: a repeat run creates no second document, version, rule
    or assignment, and leaves existing rules untouched.

    Lifecycle. The earlier single-clause fictional version is SUPERSEDED rather than
    deleted, and the organization's single assignment is repointed at the current version.
    That matters: the resolver collects every approved assignment that matches, then refuses
    to choose between two approved versions reachable from the same scope. Leaving the old
    assignment in place alongside a new one would therefore resolve *nothing*.
    """
    policy_admin_id = _sid("user:policy.admin")
    document_id = _sid("synthetic-policy-document")

    document = session.get(PolicyDocument, document_id)
    if document is None:
        document = PolicyDocument(
            id=document_id,
            organization_id=organization_id,
            title=DEMO_POLICY_DOCUMENT_TITLE,
            authoritative=False,
            notes=(
                f"{DEMO_POLICY_NATURE}. Every amount and condition in this document is "
                "invented for a demonstration and must never be used for a real "
                "reimbursement decision."
            ),
        )
        session.add(document)
        session.flush()
    else:
        # Keep the label honest as the fictional policy grows, and never let this fixture
        # present itself as authoritative.
        if document.title != DEMO_POLICY_DOCUMENT_TITLE:
            document.title = DEMO_POLICY_DOCUMENT_TITLE
        if document.authoritative:
            document.authoritative = False
        session.flush()

    # Retire the earlier fictional version so exactly one approved version is reachable.
    legacy = session.get(PolicyVersion, _sid("synthetic-policy-version"))
    if legacy is not None and legacy.review_state != PolicyReviewState.SUPERSEDED.value:
        legacy.review_state = PolicyReviewState.SUPERSEDED.value
        note = f"Superseded by the expanded {DEMO_POLICY_NATURE} policy version."
        legacy.notes = f"{legacy.notes} {note}".strip() if legacy.notes else note
        session.flush()

    version = session.get(PolicyVersion, _sid("synthetic-policy-version:v2"))
    if version is None:
        version = PolicyVersion(
            id=_sid("synthetic-policy-version:v2"),
            policy_document_id=document.id,
            version_label=DEMO_POLICY_VERSION_LABEL,
            effective_from=date(2020, 1, 1),
            review_state=PolicyReviewState.APPROVED.value,
            approved_by_user_id=policy_admin_id,
            approved_at=datetime(2020, 1, 1, tzinfo=UTC),
            notes=(
                f"{DEMO_POLICY_NATURE}; NOT an authoritative reimbursement policy. "
                "Ceilings are per claim and INR-only."
            ),
        )
        session.add(version)
        session.flush()

    for clause, category, amount in DEMO_POLICY_CLAUSES:
        rule_id = f"demo_only_ceiling_{category}"
        exists = session.execute(
            select(PolicyRule).where(
                PolicyRule.policy_version_id == version.id,
                PolicyRule.rule_id == rule_id,
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        session.add(
            PolicyRule(
                id=_sid(f"synthetic-policy-rule:ceiling:{category}"),
                policy_version_id=version.id,
                rule_id=rule_id,
                title=f"{DEMO_POLICY_NATURE}: fictional {category.replace('_', ' ')} ceiling",
                description=(
                    "Fictional per-claim ceiling seeded for demonstration only. Not a real "
                    "company rule and not an authoritative clause."
                ),
                category=category,
                evaluator_type="demo_only_category_ceiling_v1",
                parameters={"category": category, "ceiling_amount": amount},
                source_reference={
                    "document_id": str(document.id),
                    "clause": clause,
                    "policy_nature": DEMO_POLICY_NATURE,
                },
                source_clause=clause,
                source_excerpt=(
                    f"{DEMO_POLICY_NATURE}: fictional per-claim ceiling of {amount} INR for "
                    "the {category} category. Invented for this demonstration and not an "
                    "authoritative company clause.".replace("{category}", category)
                ),
                review_state=PolicyReviewState.APPROVED.value,
                is_active=True,
                validated_by_user_id=policy_admin_id,
                validated_at=datetime(2020, 1, 1, tzinfo=UTC),
            )
        )
        session.flush()

    # One organization-scoped assignment, repointed at the current version.
    assignment = session.execute(
        select(PolicyAssignment).where(
            PolicyAssignment.organization_id == organization_id,
            PolicyAssignment.scope_type == "organization",
            PolicyAssignment.scope_id == organization_id,
        )
    ).scalar_one_or_none()
    if assignment is None:
        session.add(
            PolicyAssignment(
                id=_sid("synthetic-policy-assignment:organization"),
                organization_id=organization_id,
                policy_version_id=version.id,
                scope_type="organization",
                scope_id=organization_id,
                scope_key=None,
                priority=0,
                approval_state=ApprovalState.APPROVED.value,
                effective_from=date(2020, 1, 1),
                assigned_by_user_id=policy_admin_id,
                assigned_at=datetime(2020, 1, 1, tzinfo=UTC),
                notes=f"{DEMO_POLICY_NATURE}: fictional policy assignment.",
            )
        )
        session.flush()
    elif assignment.policy_version_id != version.id:
        assignment.policy_version_id = version.id
        assignment.notes = (
            f"{DEMO_POLICY_NATURE}: fictional policy assignment, repointed to the expanded version."
        )
        session.flush()

    active_rules = (
        session.execute(
            select(PolicyRule).where(
                PolicyRule.policy_version_id == version.id,
                PolicyRule.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    return len(active_rules)
