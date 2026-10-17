"""Metadata about the running service and the contract it implements."""

from __future__ import annotations

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.core.enums import (
    DuplicateStatus,
    ExpenseChannel,
    ExpenseStatus,
    FieldSource,
    FindingResult,
    FindingSeverity,
    FindingStatus,
    FindingType,
    RecommendedAction,
    ReviewAction,
    RoleCode,
)
from app.schemas.meta import ApiMetaResponse, EnumCatalogueResponse

# Version label of the reviewed human-readable contract this build targets. Must match
# the "Contract version" line at the top of docs/api-contract.md; a contract test
# compares the two.
CONTRACT_VERSION = "1.1.1-scaffold"

# Capabilities the contract describes that this build does NOT implement. Reported
# explicitly so a caller can tell a scaffold from a finished product without
# guessing, and so nothing silently pretends to work.
UNIMPLEMENTED_CAPABILITIES: tuple[str, ...] = (
    "receipt upload and multipart handling",
    "receipt extraction (no provider selected or verified)",
    "receipt content streaming and signed URLs",
    "expense create/update/submit workflow",
    "reviewer decisions and approval tasks",
    "finding and duplicate candidate persistence and resolution",
    "policy rule execution (the registry holds zero rules)",
    "policy pre-flight check",
    "analytics and audit export",
    "production authentication (Supabase JWT validation)",
    "Supabase/S3 receipt storage adapters",
    "currency conversion",
)


def enum_catalogue() -> EnumCatalogueResponse:
    """Every canonical enum, keyed by the name used in docs/api-contract.md.

    Exposed so that clients and the contract test suite can compare their own
    expectations against the running service rather than trusting a copied list.
    """
    return EnumCatalogueResponse(
        enums={
            "ExpenseStatus": [member.value for member in ExpenseStatus],
            "ExpenseChannel": [member.value for member in ExpenseChannel],
            "RuleResult": [member.value for member in FindingResult],
            "FindingSeverity": [member.value for member in FindingSeverity],
            "FindingStatus": [member.value for member in FindingStatus],
            "FindingType": [member.value for member in FindingType],
            "DuplicateStatus": [member.value for member in DuplicateStatus],
            "ReviewAction": [member.value for member in ReviewAction],
            "RecommendedAction": [member.value for member in RecommendedAction],
            "FieldSource": [member.value for member in FieldSource],
            "RoleCode": [member.value for member in RoleCode],
        }
    )


def api_meta(config: Settings | None = None, *, implemented_routes: int = 0) -> ApiMetaResponse:
    config = config or default_settings
    return ApiMetaResponse(
        app_version=config.app_version,
        api_version="v1",
        environment=config.app_env,
        demo_mode=config.demo_routes_enabled,
        contract_version=CONTRACT_VERSION,
        implemented_endpoint_count=implemented_routes,
        unimplemented_capabilities=list(UNIMPLEMENTED_CAPABILITIES),
    )
