"""Persistence models.

Every model is imported here so that a single ``from app.models import *``
populates ``Base.metadata`` for Alembic autogenerate and for ``create_all`` in
tests. A model that is not imported here is invisible to migrations.

Relationship policy: tables declare foreign keys but no ORM ``relationship()``
collections. Service code queries explicitly. This keeps mapper configuration
trivial, avoids accidental N+1 lazy loads in request handling, and makes the
transaction boundary in the service layer the only place that decides how much
data a request touches.
"""

from app.db.base import Base
from app.models.audit import AuditEvent, IdempotencyKey
from app.models.expense import Expense, ExpenseFieldEvidence, LineItem, Trip
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
from app.models.policy import (
    PolicyAssignment,
    PolicyDocument,
    PolicyException,
    PolicyRule,
    PolicyVersion,
)
from app.models.receipt import ExtractionRun, Receipt
from app.models.review import ApprovalTask, DuplicateCandidate, Finding, ReviewDecision

__all__ = [
    "AllowanceProfile",
    "AllowanceProfileItem",
    "ApprovalTask",
    "AuditEvent",
    "Base",
    "CostCenter",
    "Department",
    "DuplicateCandidate",
    "Expense",
    "ExpenseFieldEvidence",
    "ExtractionRun",
    "Finding",
    "IdempotencyKey",
    "JobGrade",
    "LineItem",
    "OfficeLocation",
    "Organization",
    "OrganizationMembership",
    "PolicyAssignment",
    "PolicyDocument",
    "PolicyException",
    "PolicyRule",
    "PolicyVersion",
    "Receipt",
    "ReportingRelationship",
    "ReviewDecision",
    "RoleAssignment",
    "Trip",
    "User",
]
