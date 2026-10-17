"""Metadata DTOs.

These endpoints exist so that both clients and the contract tests can read the
canonical enums from the running service rather than hard-coding their own
copies. A divergence between a client's local enum list and this endpoint is a
bug that the contract test suite can detect.
"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiModel


class EnumCatalogueResponse(ApiModel):
    """Every canonical enum, keyed by the name used in docs/api-contract.md."""

    enums: dict[str, list[str]] = Field(
        ..., description="Enum name -> ordered list of permitted values."
    )


class ApiMetaResponse(ApiModel):
    """Service and contract identity."""

    app_version: str
    api_version: str
    environment: str
    demo_mode: bool
    contract_version: str = Field(
        ..., description="Version label of docs/api-contract.md this build implements."
    )
    implemented_endpoint_count: int = Field(
        ...,
        ge=0,
        description=(
            "Number of routes this build actually serves. Exposed so a caller can tell a "
            "scaffold apart from a complete implementation without guessing."
        ),
    )
    unimplemented_capabilities: list[str] = Field(
        default_factory=list,
        description=(
            "Capabilities the contract describes but this build does not implement. Reported "
            "explicitly so nothing silently pretends to work."
        ),
    )
