"""Metadata endpoints.

These exist so clients and contract tests can read the canonical enums and the
honest implementation status from the running service instead of trusting a
hand-copied list.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import settings
from app.schemas.meta import ApiMetaResponse, EnumCatalogueResponse
from app.services.meta_service import api_meta, enum_catalogue

router = APIRouter(tags=["system"])


def _count_implemented_routes(request: Request) -> int:
    """Count the paths this build actually serves.

    Reported by /meta so a caller can distinguish a scaffold from a finished
    product without reading the source. The OpenAPI document is used because
    FastAPI nests the routes contributed by ``include_router``, so iterating
    ``app.routes`` does not enumerate them.
    """
    try:
        paths = request.app.openapi().get("paths", {})
    except Exception:  # pragma: no cover - a broken schema must not break /meta
        return 0
    return sum(1 for path in paths if path.startswith(f"{settings.api_v1_prefix}/"))


@router.get(
    "/meta/enums",
    response_model=EnumCatalogueResponse,
    summary="Canonical enum catalogue",
    description=(
        "Every enumerated value in the canonical contract, keyed by the name used in "
        "docs/api-contract.md. Clients must not invent local alternatives; a divergence "
        "between a client's list and this endpoint is a bug."
    ),
)
def enums() -> EnumCatalogueResponse:
    return enum_catalogue()


@router.get(
    "/meta",
    response_model=ApiMetaResponse,
    summary="Service and contract metadata",
    description=(
        "Contract version, implemented endpoint count and the list of capabilities the "
        "contract describes but this build does not implement."
    ),
)
def meta(request: Request) -> ApiMetaResponse:
    return api_meta(settings, implemented_routes=_count_implemented_routes(request))
