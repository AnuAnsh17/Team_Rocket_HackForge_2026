"""Proofline API application entry point.

Run locally:

    uvicorn app.main:app --reload --port 8000

Interactive docs:  http://localhost:8000/docs
OpenAPI document:  http://localhost:8000/api/v1/openapi.json
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import build_api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.db.session import dispose_engine

logger = get_logger("proofline.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown.

    Startup names the capabilities that are NOT implemented. That is deliberate:
    a server that boots silently while extraction, policy rules and production
    authentication are all absent invites everyone to assume they work.
    """
    logger.info(
        "starting",
        extra={
            "environment": settings.app_env,
            "demo_mode": settings.demo_routes_enabled,
            "auth_provider": settings.auth_provider,
            "receipt_storage_backend": settings.receipt_storage_backend,
            "extraction_provider": settings.extraction_provider,
        },
    )
    if settings.demo_routes_enabled:
        logger.warning(
            "DEMO MODE IS ENABLED",
            extra={
                "detail": (
                    "Demo routes and the X-Demo-Actor-Id identity switcher are active. "
                    "This configuration must never be deployed."
                )
            },
        )
    logger.warning(
        "unimplemented capabilities",
        extra={
            "capabilities": [
                "policy rules (registry holds zero rules)",
                "expense submission, review and decision workflow",
                "production authentication",
            ],
            "detail": "See GET /api/v1/meta for the authoritative list.",
        },
    )
    yield
    extractor = getattr(app.state, "receipt_extractor", None)
    if extractor is not None and hasattr(extractor, "close"):
        extractor.close()
    dispose_engine()
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title="Proofline API",
        version=settings.app_version,
        description=(
            "Evidence-first expense auditing API. This build supports authorized draft "
            "creation and private receipt upload with OCR status tracking. OCR text is "
            "not retained or converted into structured expense fields. Production "
            "authentication, policy evaluation and review workflows remain incomplete. "
            "GET /api/v1/meta lists the outstanding capabilities."
        ),
        # The contract fixes the OpenAPI location inside the versioned prefix.
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.max_receipt_bytes = settings.receipt_max_upload_bytes

    # Correlation id and access logging wrap everything else, including errors.
    app.add_middleware(RequestContextMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "X-Demo-Actor-Id",
            "X-Demo-Organization-Id",
        ],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(app)
    # Built here, not at import time, so the demo-mode decision is made per app
    # instance and can be verified by a test.
    app.include_router(build_api_router(), prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """Send a bare request to the interactive documentation."""
        return RedirectResponse(url="/docs")

    return app


app = create_app()
