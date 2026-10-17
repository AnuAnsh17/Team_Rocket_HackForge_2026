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
* **No expense claims.** Claims are created through the application so that field
  provenance is written by the same code path a real claim uses.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import (
    AuditActorType,
    MembershipStatus,
    PolicyReviewState,
    RoleCode,
)
from app.core.logging import get_logger
from app.models.identity import OrganizationMembership, ReportingRelationship, RoleAssignment, User
from app.models.organization import (
    CostCenter,
    Department,
    OfficeLocation,
    Organization,
)
from app.models.policy import PolicyDocument, PolicyVersion
from app.schemas.demo import DemoResetResponse, DemoSeedResponse
from app.services.audit_service import audit

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

    audit(
        session,
        action="demo.seed",
        entity_type="organization",
        entity_id=organization.id,
        actor_type=AuditActorType.DEMO,
        organization_id=organization.id,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        after={"dataset": DEMO_DATASET, "policy_version_state": policy_version.review_state},
    )

    return DemoSeedResponse(
        dataset=DEMO_DATASET,
        organizations=1,
        users=len(state.users),
        memberships=len(state.memberships),
        policy_rules_activated=0,
        notes=[
            "All names, organizations and identifiers are fictional and deterministic.",
            "No job grades, allowance limits or policy rules were created: those require "
            "organizational data and a verified policy clause.",
            "The seeded policy version is intentionally left in draft state, so every claim "
            "currently evaluates to UNKNOWN rather than PASS.",
            "Use the identifiers below as X-Demo-Actor-Id values in demo mode.",
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

    users_removed = 0
    for user in session.execute(select(User).where(User.auth_provider == "demo")).scalars().all():
        session.delete(user)
        users_removed += 1

    organizations_removed = 0
    if organization is not None:
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
        organizations_removed = 1

    return DemoResetResponse(
        dataset=DEMO_DATASET,
        organizations_removed=organizations_removed,
        users_removed=users_removed,
        notes=[
            "Only the synthetic demo organization and demo-provider users were removed.",
            "Audit events are append-only and intentionally survive a reset; the reset itself "
            "is recorded as an audit event.",
        ],
    )


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
                cost_center_id=structure.get("cost_center:cc-eng"),
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
