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
CONTRACT_VERSION = "1.8.0-analytics"

# Capabilities the contract describes that this build does NOT implement. Reported
# explicitly so a caller can tell a scaffold from a finished product without
# guessing, and so nothing silently pretends to work.
UNIMPLEMENTED_CAPABILITIES: tuple[str, ...] = (
    "approval task workflow and configured review queues",
    "receipt extraction accuracy evaluation against a labelled benchmark",
    "finding and duplicate candidate persistence and resolution",
    # The pre-flight is implemented and always registered, so it is not listed here. What
    # remains unimplemented is having anything authoritative to run it against: with no
    # approved policy provisioned the registry holds no rule and every claim evaluates to
    # UNKNOWN, which is the honest result rather than a silent pass.
    "policy rule execution against a provisioned authoritative policy",
    "audit export",
    # Production authentication was listed here until Supabase JWT verification was
    # implemented and security-tested (see app/core/security.py::SupabaseAuthProvider and
    # tests/security/test_supabase_jwt.py). It is no longer a gap, so it is no longer
    # claimed as one - the list must not understate or overstate what works.
    "production receipt storage adapters (Supabase/S3)",
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
