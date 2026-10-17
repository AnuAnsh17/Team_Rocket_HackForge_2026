"""Pydantic request/response models - the canonical DTO layer.

These models are the source of the committed OpenAPI document, and therefore the
source of the generated TypeScript client that both web applications and the
mobile app consume. A change here is a contract change: update
docs/api-contract.md and regenerate the client in the same commit.
"""

from app.schemas.audit import AuditEventResponse
from app.schemas.common import (
    ErrorDetail,
    ErrorEnvelope,
    FieldErrorDetail,
    Money,
    Page,
    PageInfo,
    SourceReference,
)
from app.schemas.demo import DemoResetResponse, DemoSeedResponse
from app.schemas.expense import (
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseSummary,
)
from app.schemas.health import HealthComponent, HealthResponse
from app.schemas.identity import MembershipSummary, RoleAssignmentSummary, UserSummary
from app.schemas.meta import ApiMetaResponse, EnumCatalogueResponse
from app.schemas.policy import (
    AllowanceProfileSummary,
    PolicyAssignmentSummary,
    PolicyRuleSummary,
    PolicyVersionListResponse,
    PolicyVersionSummary,
)
from app.schemas.receipt import ReceiptResponse, ReceiptSummary
from app.schemas.review import (
    ApprovalTaskResponse,
    DuplicateCandidateResponse,
    FindingResponse,
    ReviewDecisionResponse,
)

__all__ = [
    "AllowanceProfileSummary",
    "ApiMetaResponse",
    "ApprovalTaskResponse",
    "AuditEventResponse",
    "DemoResetResponse",
    "DemoSeedResponse",
    "DuplicateCandidateResponse",
    "EnumCatalogueResponse",
    "ErrorDetail",
    "ErrorEnvelope",
    "ExpenseListResponse",
    "ExpenseResponse",
    "ExpenseSummary",
    "FieldErrorDetail",
    "FindingResponse",
    "HealthComponent",
    "HealthResponse",
    "MembershipSummary",
    "Money",
    "Page",
    "PageInfo",
    "PolicyAssignmentSummary",
    "PolicyRuleSummary",
    "PolicyVersionListResponse",
    "PolicyVersionSummary",
    "ReceiptResponse",
    "ReceiptSummary",
    "ReviewDecisionResponse",
    "RoleAssignmentSummary",
    "SourceReference",
    "UserSummary",
]
