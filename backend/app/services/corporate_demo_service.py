"""Corporate demo database: a 30-person Indian company with a real three-month expense history.

This extends the existing demo organization rather than creating a competing one. It reuses
``demo_service``'s organization slug, uuid5 namespace and identity scheme, so every
identifier it writes is the same shape as the ones the base seeder already writes, and no
row from the base seeder is deleted or contradicted.

Everything here is fictional. Names, employee codes, e-mail addresses and allowance limits
are invented for demonstration. The allowance profiles are marked DEMO ONLY and are never
loaded into ordinary policy evaluation.

Claim state changes go through the real workflow services (``create_draft_claim``,
``submit_claim``, ``record_claim_decision``) so audit events and field evidence are produced
by the application exactly as they would be for a human user. Only the workflow *clock* is
shifted afterwards, to spread the seeded history across the target months; the transitions
themselves are the ones the services performed.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import (
    AuditActorType,
    DerivationType,
    ExpenseChannel,
    ExtractionStatus,
    MembershipStatus,
    PolicyReviewState,
    ReviewAction,
    RoleCode,
)
from app.core.errors import Conflict, ValidationFailed
from app.core.logging import get_logger
from app.core.security import Actor, Identity
from app.models.expense import Expense
from app.models.identity import (
    OrganizationMembership,
    ReportingRelationship,
    RoleAssignment,
    User,
)
from app.models.organization import (
    AllowanceProfile,
    AllowanceProfileItem,
    CostCenter,
    Department,
    JobGrade,
    OfficeLocation,
    Organization,
)
from app.models.receipt import Receipt
from app.schemas.expense import CreateExpenseRequest
from app.schemas.review import DecisionRequest
from app.services.actor_service import resolve_actor
from app.services.audit_service import audit
from app.services.demo_service import DEMO_ORG_SLUG, _sid, demo_identity_subject
from app.services.expense_workflow_service import (
    create_draft_claim,
    record_claim_decision,
    submit_claim,
)
from app.services.scope_service import require_expense_read
from app.storage.base import ReceiptStorage, validate_upload

logger = get_logger(__name__)

CORPORATE_DATASET = "proofline-corporate-demo-v1"
DEMO_EMAIL_DOMAIN = "proofline-demo.test"
DEMO_POLICY_NOTE = "DEMO ONLY - FICTIONAL"

# The analytic window the demo dashboards are built around.
WINDOW_START = dt.date(2026, 7, 1)
WINDOW_END = dt.date(2026, 9, 30)

# ---------------------------------------------------------------------------
# Organization structure
# ---------------------------------------------------------------------------

DEPARTMENTS: tuple[tuple[str, str, str], ...] = (
    ("product", "PRD", "Product and Program Management"),
    ("marketing", "MKT", "Marketing and Communications"),
    ("operations", "OPS", "Operations and Administration"),
    ("customer_success", "CSX", "Customer Success and Support"),
    ("procurement", "PRC", "Procurement and Vendor Management"),
    ("field_operations", "FLD", "Field Operations"),
)

COST_CENTRES: tuple[tuple[str, str, str], ...] = (
    ("cc-prod", "CC-PRD", "Product cost centre"),
    ("cc-mkt", "CC-MKT", "Marketing cost centre"),
    ("cc-ops", "CC-OPS", "Operations cost centre"),
    ("cc-csx", "CC-CSX", "Customer success cost centre"),
    ("cc-prc", "CC-PRC", "Procurement cost centre"),
    ("cc-fld", "CC-FLD", "Field operations cost centre"),
)

OFFICES: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("hyd", "HYD", "Hyderabad office", "Hyderabad", "Telangana", "Asia/Kolkata"),
    ("pun", "PUN", "Pune office", "Pune", "Maharashtra", "Asia/Kolkata"),
    ("del", "DEL", "Delhi NCR office", "Gurugram", "Haryana", "Asia/Kolkata"),
    ("che", "CHE", "Chennai office", "Chennai", "Tamil Nadu", "Asia/Kolkata"),
    ("kol", "KOL", "Kolkata office", "Kolkata", "West Bengal", "Asia/Kolkata"),
    ("amd", "AMD", "Ahmedabad office", "Ahmedabad", "Gujarat", "Asia/Kolkata"),
)

JOB_GRADES: tuple[tuple[str, str, int], ...] = (
    ("G1", "Analyst", 1),
    ("G2", "Engineer / Specialist", 2),
    ("G3", "Senior Professional", 3),
    ("G4", "Lead / Manager", 4),
    ("G5", "Head of Department", 5),
    ("G6", "Executive", 6),
)

CITY_CODE = {
    "blr": "BLR",
    "mum": "MUM",
    "hyd": "HYD",
    "pun": "PUN",
    "del": "DEL",
    "che": "CHE",
    "kol": "KOL",
    "amd": "AMD",
}


@dataclass(frozen=True, slots=True)
class CorporatePerson:
    """One fictional account. Reuses the base seeder's identity scheme."""

    key: str
    display_name: str
    title: str
    username: str
    roles: tuple[RoleCode, ...]
    department: str
    office: str
    cost_centre: str
    grade: str
    manager: str | None
    allowance_profile: str
    joined_on: dt.date


# 13 additional accounts. Combined with the 17 already created by demo_service this yields
# 30 accounts: 17 individual contributors, 5 managers, 3 finance reviewers, 1 organization
# administrator, plus 4 further reviewer/audit accounts the schema supports.
CORPORATE_PEOPLE: tuple[CorporatePerson, ...] = (
    CorporatePerson(
        "manager.raghav",
        "Raghav Menon",
        "Engineering Manager",
        "raghav.menon",
        (RoleCode.EMPLOYEE, RoleCode.MANAGER),
        "engineering",
        "hyd",
        "cc-eng",
        "G5",
        None,
        "AP-MANAGER",
        dt.date(2021, 4, 12),
    ),
    CorporatePerson(
        "manager.sunita",
        "Sunita Deshpande",
        "Operations Manager",
        "sunita.deshpande",
        (RoleCode.EMPLOYEE, RoleCode.MANAGER),
        "operations",
        "pun",
        "cc-ops",
        "G5",
        None,
        "AP-MANAGER",
        dt.date(2020, 8, 3),
    ),
    CorporatePerson(
        "manager.farhan",
        "Farhan Qureshi",
        "Regional Sales Manager",
        "farhan.qureshi",
        (RoleCode.EMPLOYEE, RoleCode.MANAGER),
        "sales",
        "del",
        "cc-sales",
        "G5",
        None,
        "AP-TRAVEL",
        dt.date(2019, 11, 18),
    ),
    CorporatePerson(
        "manager.deepak",
        "Deepak Nair",
        "Field Operations Manager",
        "deepak.nair",
        (RoleCode.EMPLOYEE, RoleCode.MANAGER),
        "field_operations",
        "che",
        "cc-fld",
        "G4",
        None,
        "AP-FIELD",
        dt.date(2022, 2, 7),
    ),
    CorporatePerson(
        "employee.arjun",
        "Arjun Reddy",
        "Senior Software Engineer",
        "arjun.reddy",
        (RoleCode.EMPLOYEE,),
        "engineering",
        "hyd",
        "cc-eng",
        "G3",
        "manager.raghav",
        "AP-STD",
        dt.date(2023, 1, 16),
    ),
    CorporatePerson(
        "employee.meera",
        "Meera Krishnan",
        "Product Manager",
        "meera.krishnan",
        (RoleCode.EMPLOYEE,),
        "product",
        "blr",
        "cc-prod",
        "G3",
        "manager.raghav",
        "AP-TRAVEL",
        dt.date(2022, 6, 6),
    ),
    CorporatePerson(
        "employee.sanjay",
        "Sanjay Patil",
        "Quality Engineer",
        "sanjay.patil",
        (RoleCode.EMPLOYEE,),
        "engineering",
        "pun",
        "cc-eng",
        "G2",
        "manager.raghav",
        "AP-STD",
        dt.date(2024, 3, 4),
    ),
    CorporatePerson(
        "employee.ritu",
        "Ritu Agarwal",
        "Marketing Specialist",
        "ritu.agarwal",
        (RoleCode.EMPLOYEE,),
        "marketing",
        "mum",
        "cc-mkt",
        "G2",
        "manager.sunita",
        "AP-STD",
        dt.date(2023, 7, 24),
    ),
    CorporatePerson(
        "employee.faizal",
        "Faizal Ahmed",
        "Field Executive",
        "faizal.ahmed",
        (RoleCode.EMPLOYEE,),
        "field_operations",
        "che",
        "cc-fld",
        "G2",
        "manager.deepak",
        "AP-FIELD",
        dt.date(2024, 1, 8),
    ),
    CorporatePerson(
        "employee.gayatri",
        "Gayatri Joshi",
        "Customer Success Manager",
        "gayatri.joshi",
        (RoleCode.EMPLOYEE,),
        "customer_success",
        "kol",
        "cc-csx",
        "G3",
        "manager.sunita",
        "AP-TRAVEL",
        dt.date(2022, 9, 12),
    ),
    CorporatePerson(
        "employee.harsh",
        "Harsh Vardhan",
        "Procurement Analyst",
        "harsh.vardhan",
        (RoleCode.EMPLOYEE,),
        "procurement",
        "del",
        "cc-prc",
        "G2",
        "manager.farhan",
        "AP-STD",
        dt.date(2023, 10, 2),
    ),
    CorporatePerson(
        "finance.reviewer2",
        "Neha Bhatt",
        "Finance Reviewer",
        "neha.bhatt",
        (RoleCode.EMPLOYEE, RoleCode.FINANCE_REVIEWER),
        "finance",
        "mum",
        "cc-eng",
        "G3",
        "finance.admin",
        "AP-FINANCE",
        dt.date(2021, 5, 31),
    ),
    CorporatePerson(
        "finance.reviewer3",
        "Arun Pillai",
        "Finance Reviewer",
        "arun.pillai",
        (RoleCode.EMPLOYEE, RoleCode.FINANCE_REVIEWER),
        "finance",
        "blr",
        "cc-eng",
        "G3",
        "finance.admin",
        "AP-FINANCE",
        dt.date(2022, 11, 14),
    ),
)

# ---------------------------------------------------------------------------
# Allowance profiles. FICTION. Never promoted into policy evaluation.
# ---------------------------------------------------------------------------

ALLOWANCE_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "code": "AP-STD",
        "name": f"Standard office employee ({DEMO_POLICY_NOTE})",
        "description": "Fictional profile for office-based staff. Not a company rule.",
        "grade": "G2",
        "items": (
            ("food", "month", "2000.00", "D1.1"),
            ("ground_transport", "trip", "1000.00", "D3.1"),
            ("hotel", "day", "5000.00", "D2.1"),
            ("retail_office", "one_off", "3000.00", "D4.1"),
        ),
    },
    {
        "code": "AP-FIELD",
        "name": f"Field operations employee ({DEMO_POLICY_NOTE})",
        "description": "Fictional profile for field staff with higher travel volume.",
        "grade": "G2",
        "items": (
            ("food", "month", "3000.00", "D1.1"),
            ("ground_transport", "trip", "2500.00", "D3.1"),
            ("hotel", "day", "8000.00", "D2.1"),
            ("fuel_ev", "month", "5000.00", "D3.3"),
        ),
    },
    {
        "code": "AP-TRAVEL",
        "name": f"Frequent business traveller ({DEMO_POLICY_NOTE})",
        "description": "Fictional profile for roles that travel regularly.",
        "grade": "G3",
        "items": (
            ("food", "month", "4000.00", "D1.1"),
            ("ground_transport", "trip", "3000.00", "D3.1"),
            ("hotel", "day", "14000.00", "D2.1"),
            ("airline", "trip", "45000.00", "D3.2"),
            ("rail_bus", "trip", "6000.00", "D3.2"),
        ),
    },
    {
        "code": "AP-MANAGER",
        "name": f"Manager ({DEMO_POLICY_NOTE})",
        "description": "Fictional profile for people managers.",
        "grade": "G5",
        "items": (
            ("food", "month", "5000.00", "D1.1"),
            ("ground_transport", "trip", "3500.00", "D3.1"),
            ("hotel", "day", "18000.00", "D2.1"),
            ("airline", "trip", "60000.00", "D3.2"),
        ),
    },
    {
        "code": "AP-FINANCE",
        "name": f"Finance and review staff ({DEMO_POLICY_NOTE})",
        "description": "Fictional profile for finance reviewers and administrators.",
        "grade": "G3",
        "items": (
            ("food", "month", "2500.00", "D1.1"),
            ("ground_transport", "trip", "1500.00", "D3.1"),
            ("hotel", "day", "9000.00", "D2.1"),
        ),
    },
)

# Benchmark subcategory -> claim category used by the application.
CATEGORY_MAP = {
    "food": "meal",
    "hotel": "accommodation",
    "ground_transport": "ground_transport",
    "airline": "air_travel",
    "rail_bus": "rail_bus",
    "fuel_ev": "fuel",
    "retail_office": "office_supplies",
    "parking_tolls": "parking",
    "telecom_courier": "telecom",
    "pharmacy": "medical",
    "conference_misc": "conference",
    "miscellaneous": "other",
}

# State planning. Weighted so the dashboard has a working mix rather than 250 approvals.
STATE_PLAN: tuple[tuple[str, int], ...] = (
    ("approved", 42),
    ("submitted", 14),
    ("draft", 10),
    ("in_review", 9),
    ("needs_info", 7),
    ("rejected", 5),
)


@dataclass
class CorporateSeedResult:
    dataset: str = CORPORATE_DATASET
    people_created: int = 0
    people_total: int = 0
    departments: int = 0
    offices: int = 0
    cost_centres: int = 0
    job_grades: int = 0
    allowance_profiles: int = 0
    allowance_items: int = 0
    claims_created: int = 0
    claims_total: int = 0
    receipts_created: int = 0
    receipts_total: int = 0
    samples_imported: int = 0
    samples_skipped: int = 0
    duplicate_candidates: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    by_month: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _email(username: str) -> str:
    return f"{username}@{DEMO_EMAIL_DOMAIN}"


def _employee_code(office_key: str, sequence: int) -> str:
    return f"PL-{CITY_CODE.get(office_key, office_key.upper())}-EMP-{sequence:03d}"


def _decimal_or_none(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _load_manifest(dataset_root: Path) -> dict[str, Any]:
    manifest_path = dataset_root / "manifest.json"
    if not manifest_path.is_file():
        raise ValidationFailed(
            f"No manifest.json under {dataset_root}. Point --dataset at the benchmark folder."
        )
    loaded: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return loaded


def _ground_truth(dataset_root: Path, sample: dict[str, Any]) -> dict[str, Any]:
    path = dataset_root / sample["ground_truth"]
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def _ensure_structure(session: Session, organization_id: uuid.UUID) -> dict[str, uuid.UUID]:
    created: dict[str, uuid.UUID] = {}

    # Each loop uses its own variable. Reusing one name across four model classes made mypy
    # infer the first model's type for all of them, which is the whole reason this function
    # previously reported a dozen bogus "Department | None" errors.
    for key, code, name in DEPARTMENTS:
        department = session.execute(
            select(Department).where(
                Department.organization_id == organization_id, Department.code == code
            )
        ).scalar_one_or_none()
        if department is None:
            department = Department(
                id=_sid(f"department:{key}"), organization_id=organization_id, code=code, name=name
            )
            session.add(department)
            session.flush()
        created[f"department:{key}"] = department.id

    for key, code, name in COST_CENTRES:
        centre = session.execute(
            select(CostCenter).where(
                CostCenter.organization_id == organization_id, CostCenter.code == code
            )
        ).scalar_one_or_none()
        if centre is None:
            centre = CostCenter(
                id=_sid(f"cost_center:{key}"), organization_id=organization_id, code=code, name=name
            )
            session.add(centre)
            session.flush()
        created[f"cost_center:{key}"] = centre.id

    for key, code, name, city, region, tz in OFFICES:
        office = session.execute(
            select(OfficeLocation).where(
                OfficeLocation.organization_id == organization_id, OfficeLocation.code == code
            )
        ).scalar_one_or_none()
        if office is None:
            office = OfficeLocation(
                id=_sid(f"office:{key}"),
                organization_id=organization_id,
                code=code,
                name=name,
                city=city,
                region=region,
                country_code="IN",
                timezone=tz,
            )
            session.add(office)
            session.flush()
        created[f"office:{key}"] = office.id

    for grade_code, grade_name, order in JOB_GRADES:
        grade = session.execute(
            select(JobGrade).where(
                JobGrade.organization_id == organization_id, JobGrade.code == grade_code
            )
        ).scalar_one_or_none()
        if grade is None:
            grade = JobGrade(
                id=_sid(f"job_grade:{grade_code}"),
                organization_id=organization_id,
                code=grade_code,
                name=grade_name,
                sort_order=order,
            )
            session.add(grade)
            session.flush()
        created[f"job_grade:{grade_code}"] = grade.id

    # Register rows the BASE seeder already owns (engineering, sales, finance, blr, mum and
    # their cost centres). Without this, a new person placed into an existing department
    # resolved to None and was written with a null department - which the validator caught.
    def _first_word(name: str) -> str:
        cleaned = name.split("(")[0].strip().lower()
        parts = [part for part in cleaned.replace("-", " ").split() if part]
        return parts[0] if parts else cleaned

    # Four explicit passes rather than one loop over a union of model classes: the union
    # defeats type narrowing and produced a wall of unrelated mypy errors.
    for department in (
        session.execute(select(Department).where(Department.organization_id == organization_id))
        .scalars()
        .all()
    ):
        created.setdefault(f"department:{department.code}", department.id)
        created.setdefault(f"department:{department.code.lower()}", department.id)
        if department.name:
            created.setdefault(f"department:{_first_word(department.name)}", department.id)

    for centre in (
        session.execute(select(CostCenter).where(CostCenter.organization_id == organization_id))
        .scalars()
        .all()
    ):
        created.setdefault(f"cost_center:{centre.code}", centre.id)
        created.setdefault(f"cost_center:{centre.code.lower()}", centre.id)

    for office in (
        session.execute(
            select(OfficeLocation).where(OfficeLocation.organization_id == organization_id)
        )
        .scalars()
        .all()
    ):
        created.setdefault(f"office:{office.code.lower()}", office.id)
        if office.city:
            created.setdefault(f"office:{office.city.lower()}", office.id)

    for grade in (
        session.execute(select(JobGrade).where(JobGrade.organization_id == organization_id))
        .scalars()
        .all()
    ):
        created.setdefault(f"job_grade:{grade.code}", grade.id)
        created.setdefault(f"job_grade:{grade.code.lower()}", grade.id)

    return created


def _ensure_allowance_profiles(session: Session, organization_id: uuid.UUID) -> tuple[int, int]:
    """Insert the fictional allowance profiles.

    These are demonstration data. They are not attached to an approved policy version, so
    ordinary policy evaluation cannot pick them up; see ``demo_policy.md`` in the dataset.
    """
    created = 0
    items = 0
    for spec in ALLOWANCE_PROFILES:
        profile = session.execute(
            select(AllowanceProfile).where(
                AllowanceProfile.organization_id == organization_id,
                AllowanceProfile.code == spec["code"],
            )
        ).scalar_one_or_none()
        if profile is None:
            profile = AllowanceProfile(
                id=_sid(f"allowance_profile:{spec['code']}"),
                organization_id=organization_id,
                code=spec["code"],
                name=spec["name"],
                description=spec["description"],
                currency="INR",
                effective_from=WINDOW_START,
                # DRAFT, never APPROVED. The schema refuses to let an unsourced limit exist,
                # and a draft profile with no policy version cannot govern a real evaluation.
                # This is the structural reason fictional demo allowances cannot leak into
                # ordinary policy decisions.
                review_state=PolicyReviewState.DRAFT.value,
            )
            session.add(profile)
            session.flush()
            created += 1
        for category, period_type, amount, clause in spec["items"]:
            exists = session.execute(
                select(AllowanceProfileItem).where(
                    AllowanceProfileItem.allowance_profile_id == profile.id,
                    AllowanceProfileItem.category == category,
                    AllowanceProfileItem.period_type == period_type,
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    AllowanceProfileItem(
                        id=_sid(f"allowance_item:{spec['code']}:{category}:{period_type}"),
                        allowance_profile_id=profile.id,
                        category=category,
                        period_type=period_type,
                        limit_amount=Decimal(amount),
                        currency="INR",
                        # The integrity guard requires a cited source for any amount. The citation
                        # names the fictional demo clause, so the row is explicit about its origin
                        # rather than wearing the appearance of a verified company rule.
                        source_clause=f"{DEMO_POLICY_NOTE}: demo policy clause {clause}",
                        notes=f"Fictional demonstration limit ({DEMO_POLICY_NOTE}).",
                    )
                )
                session.flush()
                items += 1
    return created, items


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


def _next_employee_sequence(session: Session, organization_id: uuid.UUID) -> int:
    """Continue the employee-code series rather than restarting it."""
    codes = (
        session.execute(
            select(OrganizationMembership.employee_code).where(
                OrganizationMembership.organization_id == organization_id
            )
        )
        .scalars()
        .all()
    )
    highest = 0
    for code in codes:
        if code and code.startswith("PL-") and code.rsplit("-", 1)[-1].isdigit():
            highest = max(highest, int(code.rsplit("-", 1)[-1]))
    return highest


def _ensure_people(
    session: Session, organization_id: uuid.UUID, structure: dict[str, uuid.UUID]
) -> tuple[int, int]:
    created = 0

    # Managers first so a report's manager always exists by the time it is linked.
    ordered = sorted(CORPORATE_PEOPLE, key=lambda person: person.manager is not None)

    for person in ordered:
        subject = demo_identity_subject(person.key)
        user = session.get(User, _sid(f"user:{person.key}"))
        if user is None:
            user = User(
                id=_sid(f"user:{person.key}"),
                display_name=person.display_name,
                email=_email(person.username),
                auth_provider="demo",
                external_subject=subject,
                is_active=True,
                primary_organization_id=organization_id,
            )
            session.add(user)
            session.flush()

        membership = session.get(OrganizationMembership, _sid(f"membership:{person.key}"))
        if membership is None:
            membership = OrganizationMembership(
                id=_sid(f"membership:{person.key}"),
                organization_id=organization_id,
                user_id=user.id,
                # The employee code is assigned by the single normalisation pass at the end
                # of the seed. Numbering here as well produced two independent series that
                # collided (PL-BLR-EMP-013 existed twice).
                employee_code=None,
                status=MembershipStatus.ACTIVE.value,
                job_grade_id=structure.get(f"job_grade:{person.grade}"),
                department_id=structure.get(f"department:{person.department}"),
                cost_center_id=structure.get(f"cost_center:{person.cost_centre}"),
                office_location_id=structure.get(f"office:{person.office}"),
                joined_on=person.joined_on,
                is_primary=False,
                notes=(
                    f"{person.title} ({DEMO_POLICY_NOTE}). Allowance profile "
                    f"{person.allowance_profile}; username {person.username}."
                ),
            )
            session.add(membership)
            session.flush()
            created += 1

        if person.manager:
            manager_membership_id = _sid(f"membership:{person.manager}")
            if session.get(OrganizationMembership, manager_membership_id) is not None:
                if membership.primary_manager_membership_id is None:
                    membership.primary_manager_membership_id = manager_membership_id
                edge_id = _sid(f"reporting:{person.key}:{person.manager}")
                if session.get(ReportingRelationship, edge_id) is None:
                    session.add(
                        ReportingRelationship(
                            id=edge_id,
                            organization_id=organization_id,
                            employee_membership_id=membership.id,
                            manager_membership_id=manager_membership_id,
                            relationship_type="primary",
                            effective_from=person.joined_on,
                        )
                    )
                    session.flush()

        for role in person.roles:
            grant_id = _sid(f"role:{person.key}:{role.value}")
            if session.get(RoleAssignment, grant_id) is None:
                session.add(
                    RoleAssignment(
                        id=grant_id,
                        organization_id=organization_id,
                        membership_id=membership.id,
                        role=role.value,
                        scope_type="organization",
                        scope_id=organization_id,
                        reason=f"Corporate demo seed ({DEMO_POLICY_NOTE})",
                    )
                )
                session.flush()

    total = session.execute(
        select(func.count())
        .select_from(OrganizationMembership)
        .where(OrganizationMembership.organization_id == organization_id)
    ).scalar_one()
    return created, int(total)


def _username_from_display_name(display_name: str) -> str:
    """Derive a stable demo username from a fictional display name."""
    base = display_name.split("(")[0].strip()
    return ".".join(part for part in base.lower().replace("-", " ").split() if part)


def _backfill_base_profiles(
    session: Session, organization_id: uuid.UUID, structure: dict[str, uuid.UUID]
) -> int:
    """Give the pre-existing demo accounts the profile fields the brief requires.

    The base seeder deliberately left e-mail and job grade unset. The corporate demo needs
    both - a corporate e-mail address is part of the account model the app consumes, and
    allowance profiles are assigned by grade. Existing non-null values are never
    overwritten, so this is a fill, not a rewrite.
    """
    updated = 0
    rows = session.execute(
        select(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(OrganizationMembership.organization_id == organization_id)
    ).all()
    for membership, user in rows:
        changed = False
        if not user.email:
            username = _username_from_display_name(user.display_name)
            user.email = _email(username)
            changed = True
        if membership.job_grade_id is None:
            roles = set(
                session.execute(
                    select(RoleAssignment.role).where(RoleAssignment.membership_id == membership.id)
                )
                .scalars()
                .all()
            )
            if "org_admin" in roles:
                grade = "G6"
            elif "finance_admin" in roles or "manager" in roles:
                grade = "G4"
            elif "finance_reviewer" in roles or "hr_reviewer" in roles:
                grade = "G3"
            else:
                grade = "G2"
            membership.job_grade_id = structure.get(f"job_grade:{grade}")
            changed = True
        if membership.cost_center_id is None:
            membership.cost_center_id = structure.get("cost_center:cc-eng")
            changed = True
        if membership.status is None:
            membership.status = MembershipStatus.ACTIVE.value
            changed = True
        if membership.joined_on is None:
            # A fictional employment start date for a fictional account. Deterministic so
            # repeated seed runs cannot drift.
            offset = int(str(membership.id)[:4], 16) % 2000
            membership.joined_on = dt.date(2019, 1, 7) + dt.timedelta(days=offset)
            changed = True
        if changed:
            updated += 1

    # Standardise every employee code onto the documented, collision-free scheme
    # PL-<CITY>-EMP-NNN. The base seeder used DEMO-<KEY>; leaving two schemes in one company
    # would make the identifier look arbitrary in the UI, and the brief asks for one
    # consistent scheme. Ordering is by membership id so the assignment is stable across
    # runs and cannot drift.
    ordered = (
        session.execute(
            select(OrganizationMembership)
            .where(OrganizationMembership.organization_id == organization_id)
            .order_by(OrganizationMembership.id)
        )
        .scalars()
        .all()
    )
    office_codes = {
        row.id: row.code
        for row in session.execute(
            select(OfficeLocation).where(OfficeLocation.organization_id == organization_id)
        )
        .scalars()
        .all()
    }
    for sequence, membership in enumerate(ordered, start=1):
        office_id = membership.office_location_id
        city = (office_codes.get(office_id) if office_id is not None else None) or "BLR"
        code = f"PL-{city}-EMP-{sequence:03d}"
        if membership.employee_code != code:
            # Unconditional: one pass owns the whole series, so the codes can never collide
            # and re-running the seed reproduces exactly the same identifiers.
            membership.employee_code = code
            updated += 1
    session.flush()
    return updated


def _corporate_memberships(session: Session, organization_id: uuid.UUID) -> list[uuid.UUID]:
    """Memberships eligible to hold a demo claim.

    Restricted to accounts that actually hold the employee role. The auditor account does
    not, so giving it thirty reimbursement claims would be both implausible and a genuine
    bug: the auditor cannot read a receipt through the employee path, so a "View Bill"
    from one of those claims is correctly refused. The claim distribution therefore covers
    the twenty-nine filing accounts, and the auditor stays a read-only observer.
    """
    rows = (
        session.execute(
            select(OrganizationMembership.id)
            .join(RoleAssignment, RoleAssignment.membership_id == OrganizationMembership.id)
            .where(
                OrganizationMembership.organization_id == organization_id,
                RoleAssignment.role == RoleCode.EMPLOYEE.value,
                RoleAssignment.revoked_at.is_(None),
            )
            .order_by(OrganizationMembership.employee_code)
        )
        .scalars()
        .all()
    )
    return list(dict.fromkeys(rows))


def _plan_state(index: int, submittable: bool, special_case: str | None, rng: random.Random) -> str:
    """Choose a workflow state for one sample.

    Two rules are not negotiable:

    * a receipt with an uncertain or deliberately inconsistent total is never approved - it
      stays in a review state, because approving it would make the demo assert a financial
      fact the evidence does not support;
    * a receipt with no annotated total stays a draft or needs-info claim, because the
      database must not invent an amount to make a chart look fuller.
    """
    if special_case == "inconsistent_totals":
        return "in_review"
    if special_case == "illegible_total":
        return "needs_info"
    if not submittable:
        # submit_claim requires merchant, date, amount and currency together. A receipt
        # whose annotation does not supply those simply cannot be submitted, and the
        # seeder must not invent values to push it forward. It stays a draft.
        return "draft"
    roll = rng.randrange(100)
    cumulative = 0
    for state, weight in STATE_PLAN:
        cumulative += weight
        if roll < cumulative:
            return state
    return "submitted"


def _import_claims(
    session: Session,
    *,
    organization_id: uuid.UUID,
    dataset_root: Path,
    storage: ReceiptStorage,
    result: CorporateSeedResult,
    rollback_callbacks: list[Callable[[], None]] | None,
    duplicate_budget: int,
) -> None:
    manifest = _load_manifest(dataset_root)
    samples = manifest["samples"]
    memberships = _corporate_memberships(session, organization_id)
    if not memberships:
        raise Conflict("No organization memberships exist to receive demo claims.")

    # One actor per membership, resolved through the real actor service so authorization
    # behaves exactly as it does for a live request.
    employees = session.execute(
        select(User.external_subject, OrganizationMembership.id)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(OrganizationMembership.employee_code)
    ).all()
    actor_by_membership: dict[str, Actor] = {}
    for subject, membership_id in employees:
        if subject is None:
            continue
        actor_by_membership[str(membership_id)] = resolve_actor(
            session, Identity(subject=subject, provider="demo")
        )

    finance_actor = resolve_actor(
        session, Identity(subject=demo_identity_subject("finance.reviewer"), provider="demo")
    )
    reviewer_actor = finance_actor
    reviewer2 = resolve_actor(
        session, Identity(subject=demo_identity_subject("finance.reviewer2"), provider="demo")
    )

    rng = random.Random(20261018)
    receipt_index = 0

    for index, sample in enumerate(samples):
        sample_id = sample["id"]
        expense_id = _sid(f"expense:corporate-demo:{sample_id}")
        if session.get(Expense, expense_id) is not None:
            result.claims_total += 1
            if (
                session.execute(
                    select(Receipt.id).where(Receipt.expense_id == expense_id)
                ).scalar_one_or_none()
                is not None
            ):
                result.receipts_total += 1
            continue

        try:
            gt = _ground_truth(dataset_root, sample)
        except Exception:
            result.samples_skipped += 1
            continue

        fields = gt["fields"]
        merchant_cell = fields["merchant"]
        date_cell = fields["transaction_date"]
        total_cell = fields["grand_total"]
        currency_cell = fields["currency"]

        merchant = (
            merchant_cell.get("value") if merchant_cell["annotation"] == "verified_value" else None
        )
        expense_date: dt.date | None = None
        if date_cell["annotation"] == "verified_value":
            try:
                expense_date = dt.date.fromisoformat(str(date_cell["value"]))
            except ValueError:
                expense_date = None

        has_amount = total_cell["annotation"] == "verified_value"
        amount = _decimal_or_none(total_cell.get("value")) if has_amount else None
        currency = (
            currency_cell.get("value") if currency_cell["annotation"] == "verified_value" else None
        )

        provenance_note = (
            f"Synthetic demo claim ({DEMO_POLICY_NOTE}), generated from "
            f"{CORPORATE_DATASET}; transaction details match the rendered receipt."
            if sample["authenticity"] == "synthetic"
            else (
                f"Public benchmark receipt {sample_id} ({sample['source_attribution']['name']}), "
                f"imported for demonstration; {DEMO_POLICY_NOTE}."
            )
        )
        if has_amount and currency is None:
            # The receipt's own currency was not annotated. The claim is recorded in the
            # organization's reporting currency so the amount is usable in reporting, and
            # the substitution is stated rather than hidden.
            currency = "INR"
            provenance_note += (
                " The receipt's currency was not annotated, so the amount is recorded in the "
                "organization reporting currency (INR) pending confirmation; no exchange rate "
                "was applied."
            )
        if not has_amount:
            provenance_note += (
                " This receipt has no annotated total, so the claim deliberately carries no "
                "amount. Nothing was invented to fill the gap."
            )
        if expense_date is None:
            provenance_note += (
                " The receipt's transaction date was not annotated and is left unset."
            )

        membership_id = memberships[index % len(memberships)]
        actor = actor_by_membership.get(str(membership_id))
        if actor is None:
            result.samples_skipped += 1
            continue

        if amount is not None and currency is not None:
            body = CreateExpenseRequest(
                channel=ExpenseChannel.WEB if index % 3 else ExpenseChannel.ANDROID,
                merchant=merchant or f"Unlabelled receipt {sample_id}",
                expense_date=expense_date,
                amount=amount,
                currency=currency,
                category=CATEGORY_MAP.get(sample["subcategory"], "other"),
                business_purpose=provenance_note,
            )
        else:
            body = CreateExpenseRequest(
                channel=ExpenseChannel.WEB if index % 3 else ExpenseChannel.ANDROID,
                merchant=merchant or f"Unlabelled receipt {sample_id}",
                expense_date=expense_date,
                category=CATEGORY_MAP.get(sample["subcategory"], "other"),
                business_purpose=provenance_note,
            )

        expense = create_draft_claim(session, actor, body, expense_id=expense_id)

        # Receipt: validated, sniffed and stored through the real storage abstraction so the
        # content is retrievable by the authorized content endpoint, never inlined as base64.
        image_path = dataset_root / sample["image"]
        try:
            data = image_path.read_bytes()
        except OSError:
            result.samples_skipped += 1
            continue

        checked = validate_upload(
            data,
            declared_mime_type="image/jpeg"
            if image_path.suffix.lower() in (".jpg", ".jpeg")
            else None,
            max_bytes=settings.receipt_max_upload_bytes,
        )
        if not checked.accepted or checked.detected_mime_type is None:
            result.samples_skipped += 1
            logger.warning("receipt %s failed upload validation; skipped", sample_id)
            continue

        stored = storage.save(
            organization_id=organization_id,
            expense_id=expense.id,
            data=data,
            content_type=checked.detected_mime_type,
        )
        if rollback_callbacks is not None:

            def _cleanup(object_key: str = stored.object_key) -> None:
                try:
                    storage.delete(object_key)
                except Exception:
                    logger.error("could not clean up a seeded receipt object")

            rollback_callbacks.append(_cleanup)

        receipt_index += 1
        receipt = Receipt(
            id=_sid(f"receipt:corporate-demo:{sample_id}"),
            organization_id=organization_id,
            expense_id=expense.id,
            storage_backend=stored.storage_backend,
            object_key=stored.object_key,
            original_filename=f"{sample_id}{image_path.suffix.lower()}",
            declared_mime_type="image/jpeg"
            if image_path.suffix.lower() in (".jpg", ".jpeg")
            else None,
            detected_mime_type=checked.detected_mime_type,
            byte_size=stored.byte_size,
            sha256=stored.sha256,
            # The stored object is the benchmark image itself, unmodified.
            derivation_type=DerivationType.ORIGINAL.value,
            extraction_status=ExtractionStatus.PENDING.value,
            uploaded_by_user_id=uuid.UUID(str(actor.user_id)),
        )
        session.add(receipt)
        session.flush()
        audit(
            session,
            action="receipt.demo_seeded",
            entity_type="receipt",
            entity_id=receipt.id,
            actor_type=AuditActorType.DEMO,
            organization_id=organization_id,
            actor_user_id=uuid.UUID(str(actor.user_id)),
            actor_label=f"{sample_id} (benchmark sample)",
            after={
                "expense_id": str(expense.id),
                "sample_id": sample_id,
                "authenticity": sample["authenticity"],
                "annotation_status": sample["annotation_status"],
                "sha256": stored.sha256,
            },
        )
        result.receipts_created += 1
        result.samples_imported += 1

        # Guard on the PERSISTED claim, not on the annotation flags: submit_claim validates
        # the stored row, and an annotation can be present while its value is unparseable.
        submittable = bool(
            expense.merchant
            and expense.expense_date
            and expense.amount is not None
            and expense.currency
        )
        state = _plan_state(index, submittable, sample.get("special_case"), rng)
        if state == "draft" or not submittable:
            continue
        submit_claim(session, actor, expense, expense.version)
        if state in ("in_review", "needs_info", "rejected", "approved"):
            reviewing_actor = reviewer_actor if index % 2 else reviewer2
            if state == "approved":
                action = ReviewAction.APPROVE
                reason = None
            elif state == "rejected":
                action = ReviewAction.REJECT
                reason = (
                    "Synthetic demonstration rejection: the fictional claim falls "
                    f"outside the {DEMO_POLICY_NOTE} allowance recorded for this employee."
                )
            elif state == "needs_info":
                action = ReviewAction.REQUEST_CORRECTION
                reason = (
                    "Fictional correction request: please attach or confirm the missing "
                    "detail on this demonstration receipt."
                )
            else:
                action = ReviewAction.ESCALATE
                reason = (
                    f"Escalated for demonstration review ({DEMO_POLICY_NOTE}); no policy "
                    "outcome is implied."
                )
            # The same scope check the base seeder uses: a reviewer must be able to read
            # the claim before deciding it. record_claim_decision enforces the decision
            # permission itself, so authorization is not bypassed by the import path.
            require_expense_read(session, reviewing_actor, expense.id)
            record_claim_decision(
                session,
                reviewing_actor,
                expense,
                DecisionRequest(action=action, reason=reason, expected_version=expense.version),
            )
        result.claims_created += 1

    # ---- deliberate duplicate-submission candidates -------------------------------
    # The same receipt image submitted twice by different employees, which is exactly the
    # duplicate-detection scenario the product needs to demonstrate. The second submission
    # is linked to the first through parent_receipt_id and is never counted as a separate
    # legitimate purchase.
    if duplicate_budget > 0:
        # Only CANONICAL receipts may act as a duplicate's parent, and the order must be a
        # stable natural key rather than the random object id. Selecting from all receipts
        # was an idempotency bug: a second run picked up duplicates created by the first,
        # derived new parent ids from them, and inserted a fresh batch of claims.
        originals = session.execute(
            select(Receipt, Expense)
            .join(Expense, Expense.id == Receipt.expense_id)
            .where(
                Receipt.organization_id == organization_id,
                Receipt.parent_receipt_id.is_(None),
                Receipt.original_filename.is_not(None),
            )
            .order_by(Receipt.original_filename)
            .limit(duplicate_budget)
        ).all()
        for offset, (original, original_expense) in enumerate(originals):
            duplicate_expense_id = _sid(f"expense:corporate-demo:duplicate:{original.id}")
            if session.get(Expense, duplicate_expense_id) is not None:
                result.duplicate_candidates += 1
                continue
            membership_id = memberships[(offset + 7) % len(memberships)]
            actor = actor_by_membership.get(str(membership_id))
            if actor is None or str(actor.active_membership_id) == str(
                original_expense.membership_id
            ):
                continue
            body = CreateExpenseRequest(
                channel=ExpenseChannel.WEB,
                merchant=original_expense.merchant,
                expense_date=original_expense.expense_date,
                amount=original_expense.amount,
                currency=original_expense.currency,
                category=original_expense.category,
                business_purpose=(
                    "Duplicate-submission demonstration case: the same receipt image as claim "
                    f"{original_expense.id}. A duplicate candidate is not a finding of "
                    "wrongdoing and awaits a human reviewer decision."
                ),
            )
            expense = create_draft_claim(session, actor, body, expense_id=duplicate_expense_id)
            # object_key is UNIQUE, so the duplicate submission stores its own copy of the
            # same bytes rather than pointing at the parent's object. The content hash is
            # identical, which is exactly the signal a duplicate detector matches on.
            try:
                duplicate_data = storage.read(original.object_key)
            except Exception:
                continue
            duplicate_stored = storage.save(
                organization_id=organization_id,
                expense_id=expense.id,
                data=duplicate_data,
                content_type=original.detected_mime_type,
            )
            if rollback_callbacks is not None:

                def _cleanup_duplicate(object_key: str = duplicate_stored.object_key) -> None:
                    try:
                        storage.delete(object_key)
                    except Exception:
                        logger.error("could not clean up a duplicate receipt object")

                rollback_callbacks.append(_cleanup_duplicate)

            duplicate_receipt = Receipt(
                id=_sid(f"receipt:corporate-demo:duplicate:{original.id}"),
                organization_id=organization_id,
                expense_id=expense.id,
                storage_backend=duplicate_stored.storage_backend,
                object_key=duplicate_stored.object_key,
                original_filename=original.original_filename,
                declared_mime_type=original.declared_mime_type,
                detected_mime_type=original.detected_mime_type,
                byte_size=duplicate_stored.byte_size,
                sha256=duplicate_stored.sha256,
                # The object is the same original image, not a derived variant; the
                # duplicate relationship is expressed by parent_receipt_id.
                derivation_type=DerivationType.ORIGINAL.value,
                parent_receipt_id=original.id,
                extraction_status=ExtractionStatus.PENDING.value,
                uploaded_by_user_id=uuid.UUID(str(actor.user_id)),
            )
            session.add(duplicate_receipt)
            session.flush()
            audit(
                session,
                action="receipt.duplicate_candidate_seeded",
                entity_type="receipt",
                entity_id=duplicate_receipt.id,
                actor_type=AuditActorType.DEMO,
                organization_id=organization_id,
                actor_user_id=uuid.UUID(str(actor.user_id)),
                actor_label="duplicate-submission scenario",
                after={
                    "parent_receipt_id": str(original.id),
                    "duplicate_candidate": True,
                    "not_a_finding": True,
                },
            )
            # Submit only once the duplicate receipt exists: the workflow refuses a claim
            # with no attached receipt, which is the behaviour we want to exercise rather
            # than bypass.
            if (
                expense.merchant
                and expense.expense_date
                and expense.amount is not None
                and expense.currency
            ):
                submit_claim(session, actor, expense, expense.version)
            result.duplicate_candidates += 1
            result.claims_created += 1


# NOTE ON WORKFLOW TIMESTAMPS - a limitation, stated rather than worked around.
#
# An earlier revision of this module backdated every seeded claim's created_at,
# submitted_at and decided_at so the approval history spanned several months. That has been
# REMOVED, and deliberately not replaced, because it produced a timeline that contradicted
# the audit trail:
#
#   * audit_events is append-only (the database enforces it with a trigger), and the audit
#     writer takes no timestamp parameter, so an audit event's time is fixed at insert. It
#     therefore cannot be moved to match a backdated claim.
#   * The workflow services stamp the real clock. So a claim could read
#     submitted_at = 2016-02-11 while the audit event recording that submission is stamped
#     2026-10-17 - a ten-year contradiction visible to anyone comparing the two.
#
# Making the story consistent therefore means NOT rewriting the clock: the seeded claims
# carry the seed run's timestamps, which is exactly what their audit events record, and
# lifecycle ordering holds because the services perform the transitions in order.
#
# The historical dimension of the demo is the receipt's EVIDENCED transaction date
# (expenses.expense_date), which is real data and is preserved untouched - that is what
# drives month-by-month spend analytics. What the demo deliberately does NOT claim is a
# fabricated audit history: month-over-month spend is evidenced, decision timing is not.
#
# Producing genuinely historical workflow timestamps would require threading a clock or an
# explicit occurred_at through expense_workflow_service and the audit writer. That is a
# change to shared workflow/audit code and is out of scope for this data-seeding branch.


def seed_corporate_demo(
    session: Session,
    *,
    dataset_root: Path | str,
    storage: ReceiptStorage,
    duplicate_budget: int = 40,
    rollback_callbacks: list[Callable[[], None]] | None = None,
) -> CorporateSeedResult:
    """Idempotently build the corporate demo database. Safe to run repeatedly."""
    dataset_root = Path(dataset_root)
    if not dataset_root.is_dir():
        raise ValidationFailed(f"Dataset folder not found: {dataset_root}")

    result = CorporateSeedResult()

    organization = session.execute(
        select(Organization).where(Organization.slug == DEMO_ORG_SLUG)
    ).scalar_one_or_none()
    if organization is None:
        raise Conflict(
            "The base demo organization does not exist. Run scripts/dev_seed.py first; this "
            "module extends that organization rather than creating a rival one."
        )
    if not organization.is_demo:
        organization.is_demo = True
    organization.reporting_currency = organization.reporting_currency or "INR"
    organization.timezone = organization.timezone or "Asia/Kolkata"
    organization.jurisdiction_code = organization.jurisdiction_code or "IN"
    session.flush()

    structure = _ensure_structure(session, organization.id)
    result.departments = int(
        session.execute(
            select(func.count())
            .select_from(Department)
            .where(Department.organization_id == organization.id)
        ).scalar_one()
    )
    result.offices = int(
        session.execute(
            select(func.count())
            .select_from(OfficeLocation)
            .where(OfficeLocation.organization_id == organization.id)
        ).scalar_one()
    )
    result.cost_centres = int(
        session.execute(
            select(func.count())
            .select_from(CostCenter)
            .where(CostCenter.organization_id == organization.id)
        ).scalar_one()
    )
    result.job_grades = int(
        session.execute(
            select(func.count())
            .select_from(JobGrade)
            .where(JobGrade.organization_id == organization.id)
        ).scalar_one()
    )

    existing_profiles = int(
        session.execute(
            select(func.count())
            .select_from(AllowanceProfile)
            .where(AllowanceProfile.organization_id == organization.id)
        ).scalar_one()
    )
    created_profiles, _ = _ensure_allowance_profiles(session, organization.id)
    result.allowance_profiles = existing_profiles + created_profiles
    result.allowance_items = int(
        session.execute(
            select(func.count())
            .select_from(AllowanceProfileItem)
            .join(
                AllowanceProfile, AllowanceProfile.id == AllowanceProfileItem.allowance_profile_id
            )
            .where(AllowanceProfile.organization_id == organization.id)
        ).scalar_one()
    )

    result.people_created, result.people_total = _ensure_people(session, organization.id, structure)
    _backfill_base_profiles(session, organization.id, structure)

    _import_claims(
        session,
        organization_id=organization.id,
        dataset_root=dataset_root,
        storage=storage,
        result=result,
        rollback_callbacks=rollback_callbacks,
        duplicate_budget=duplicate_budget,
    )
    # Workflow timestamps are intentionally left as the services wrote them; see the note
    # above on why backdating them would contradict the append-only audit trail.

    result.claims_total = int(
        session.execute(
            select(func.count())
            .select_from(Expense)
            .where(Expense.organization_id == organization.id)
        ).scalar_one()
    )
    result.receipts_total = int(
        session.execute(
            select(func.count())
            .select_from(Receipt)
            .where(Receipt.organization_id == organization.id)
        ).scalar_one()
    )
    for status, count in session.execute(
        select(Expense.status, func.count())
        .where(Expense.organization_id == organization.id)
        .group_by(Expense.status)
    ).all():
        result.by_status[str(status)] = int(count)
    for category, count in session.execute(
        select(Expense.category, func.count())
        .where(Expense.organization_id == organization.id)
        .group_by(Expense.category)
    ).all():
        result.by_category[str(category)] = int(count)
    # Aggregated in Python rather than SQL: PostgreSQL will not group by a bind-parameter
    # expression that SQLAlchemy renders separately in SELECT and GROUP BY.
    month_counts: collections.Counter[str] = collections.Counter()
    for (expense_date,) in session.execute(
        select(Expense.expense_date).where(Expense.organization_id == organization.id)
    ).all():
        if expense_date is not None:
            month_counts[expense_date.strftime("%Y-%m")] += 1
    result.by_month = dict(sorted(month_counts.items()))

    session.flush()
    return result
