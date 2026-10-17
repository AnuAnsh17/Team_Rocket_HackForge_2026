"""Canonical Proofline enums.

This module is the single source of truth for every enumerated value in the
system. Persistence models, Pydantic schemas and the OpenAPI document all import
from here, which is what stops the Android app, the employee web portal and the
internal console from drifting apart.

Rules (see AGENTS.md and docs/api-contract.md):
  - Enum values are stable, machine-readable identifiers. They are part of the
    public contract. Renaming one is a contract change and requires updating
    docs/api-contract.md, the generated OpenAPI schema and both clients.
  - Nothing in this module encodes a policy threshold, limit, city cap, time
    window or exchange rate. Enumerations describe *kinds*, never *amounts*.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ALLOWANCE_PERIOD_TYPES",
    "APPROVAL_TASK_STATUSES",
    "ApprovalState",
    "ApprovalTaskStatus",
    "AuditActorType",
    "DerivationType",
    "DuplicateStatus",
    "ExpenseChannel",
    "ExpenseFieldName",
    "ExpenseStatus",
    "ExtractionStatus",
    "FieldSource",
    "FindingResult",
    "FindingSeverity",
    "FindingStatus",
    "FindingType",
    "LineItemEligibility",
    "MembershipStatus",
    "PolicyAssignmentScopeType",
    "PolicyExceptionType",
    "PolicyReviewState",
    "RecommendedAction",
    "ReviewAction",
    "RoleCode",
    "StorageBackend",
    "TripStatus",
]


class ExpenseStatus(StrEnum):
    """Workflow status of an expense claim.

    Deliberately NOT used to represent individual findings: a claim can carry
    many findings while holding exactly one workflow status.

    ``WITHDRAWN`` is reserved. No endpoint currently produces it; see
    docs/api-contract.md section 5 for the explanation.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    NEEDS_INFO = "needs_info"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ExpenseChannel(StrEnum):
    """How a claim entered the system.

    ``EMAIL_SIMULATED`` is demo-only and must never be presented as a real
    email integration.
    """

    ANDROID = "android"
    WEB = "web"
    BULK = "bulk"
    EMAIL_SIMULATED = "email_simulated"


class TripStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FieldSource(StrEnum):
    """Provenance of a single expense field value.

    Employee-entered values must never masquerade as receipt evidence, which is
    why the provenance travels with the value instead of being inferred.
    """

    RECEIPT_EXTRACTION = "receipt_extraction"
    EMPLOYEE_INPUT = "employee_input"
    REVIEWER_CORRECTION = "reviewer_correction"
    IMPORTED_DATA = "imported_data"
    COMPUTED = "computed"


class ExpenseFieldName(StrEnum):
    """Fields that carry per-field provenance and correction history."""

    MERCHANT = "merchant"
    EXPENSE_DATE = "expense_date"
    AMOUNT = "amount"
    CURRENCY = "currency"
    CATEGORY = "category"
    BUSINESS_PURPOSE = "business_purpose"
    CLIENT_NAME = "client_name"
    ATTENDEE_COUNT = "attendee_count"
    TRIP_ID = "trip_id"
    RECEIPT_NUMBER = "receipt_number"


class FindingResult(StrEnum):
    """Tri-state rule outcome. UNKNOWN must never silently pass."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class FindingSeverity(StrEnum):
    """Impact and routing weight. Never a statement about guilt or fraud."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class FindingStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class FindingType(StrEnum):
    """Stable finding classifiers.

    This list is intentionally short and structural. Adding a member is a
    contract change. No member implies fraud.
    """

    REQUIRED_FIELD_MISSING = "required_field_missing"
    FIELD_UNCERTAIN = "field_uncertain"
    ARITHMETIC_MISMATCH = "arithmetic_mismatch"
    INDIVIDUAL_LIMIT_EXCEEDED = "individual_limit_exceeded"
    AGGREGATE_LIMIT_EXCEEDED = "aggregate_limit_exceeded"
    INELIGIBLE_CATEGORY = "ineligible_category"
    INELIGIBLE_LINE_ITEM = "ineligible_line_item"
    MISSING_POLICY_CONTEXT = "missing_policy_context"
    POLICY_CONFLICT = "policy_conflict"
    DUPLICATE_CANDIDATE = "duplicate_candidate"
    APPROVAL_REQUIRED = "approval_required"
    EXTRACTION_FAILED = "extraction_failed"


class RecommendedAction(StrEnum):
    """Advisory next step attached to a finding.

    Distinct from :class:`ReviewAction` on purpose. A recommendation is advice
    attached to a finding; a ReviewAction is a decision an authorized reviewer
    actually executes. Conflating them would imply the backend had already
    decided the claim.
    """

    NONE = "none"
    REVIEW = "review"
    REQUEST_CORRECTION = "request_correction"
    ESCALATE = "escalate"


class ReviewAction(StrEnum):
    """A reviewer/approver decision that actually transitions a claim."""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CORRECTION = "request_correction"
    ESCALATE = "escalate"


class DuplicateStatus(StrEnum):
    """Candidate lifecycle. A candidate is never a confirmed duplicate."""

    OPEN = "open"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class DerivationType(StrEnum):
    """How a derived receipt object relates to its parent."""

    ORIGINAL = "original"
    CROP = "crop"
    ROTATION = "rotation"
    RECOMPRESSION = "recompression"
    THUMBNAIL = "thumbnail"


class LineItemEligibility(StrEnum):
    """Per-line-item eligibility. UNKNOWN is a legitimate, non-accusatory state."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_EVALUATED = "not_evaluated"


ALLOWANCE_PERIOD_TYPES = (
    "day",
    "week",
    "month",
    "quarter",
    "year",
    "trip",
    "one_off",
)
APPROVAL_TASK_STATUSES = ("pending", "in_progress", "approved", "rejected", "cancelled", "skipped")


class MembershipStatus(StrEnum):
    """Employment state of an organization membership."""

    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    INVITED = "invited"


class RoleCode(StrEnum):
    """Role identifiers granted through organization memberships.

    A privileged-sounding role name never implies permissions. The actual
    permission set for each role lives in app/core/permissions.py and is
    documented in docs/authorization-matrix.md.
    """

    EMPLOYEE = "employee"
    MANAGER = "manager"
    HR_REVIEWER = "hr_reviewer"
    FINANCE_REVIEWER = "finance_reviewer"
    FINANCE_ADMIN = "finance_admin"
    ORG_ADMIN = "org_admin"
    POLICY_ADMIN = "policy_admin"
    AUDITOR = "auditor"
    SERVICE = "service"


class PolicyReviewState(StrEnum):
    """Editorial/review state of policy artefacts. Only APPROVED governs."""

    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class PolicyAssignmentScopeType(StrEnum):
    """Scope dimensions along which a policy version can be assigned.

    Supported dimensions, NOT a claim that every organization uses all of them.
    Precedence between scopes is configuration, not an assumption: see
    docs/role-policy-hierarchy.md.
    """

    ORGANIZATION = "organization"
    LEGAL_ENTITY = "legal_entity"
    JURISDICTION = "jurisdiction"
    OFFICE_LOCATION = "office_location"
    DEPARTMENT = "department"
    COST_CENTER = "cost_center"
    JOB_GRADE = "job_grade"
    TRIP = "trip"
    EXPENSE_CATEGORY = "expense_category"
    EMPLOYEE = "employee"


class PolicyExceptionType(StrEnum):
    """Explicit, reviewed, time-bounded deviation from an assigned policy."""

    LIMIT_OVERRIDE = "limit_override"
    CATEGORY_ALLOWANCE = "category_allowance"
    APPROVAL_WAIVER = "approval_waiver"
    OTHER = "other"


class ApprovalTaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class ApprovalState(StrEnum):
    """Approval state of a policy/allowance artefact itself."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AuditActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    SERVICE = "service"
    DEMO = "demo"


class StorageBackend(StrEnum):
    LOCAL = "local"
    SUPABASE = "supabase"
    S3 = "s3"
