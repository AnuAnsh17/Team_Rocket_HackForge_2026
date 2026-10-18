"""Proofline API application entry point.

Run locally:

    uvicorn app.main:app --reload --port 8000

Interactive docs:  http://localhost:8000/docs
OpenAPI document:  http://localhost:8000/api/v1/openapi.json
"""

from __future__ import annotations

import asyncio
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
from app.db.session import dispose_engine, get_session_factory
from app.extraction.factory import build_receipt_extractor
from app.extraction.worker import ExtractionJobWorker
from app.services.meta_service import UNIMPLEMENTED_CAPABILITIES
from app.storage.factory import build_receipt_storage

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
            # Derived from the same tuple /api/v1/meta serves, so there is one list.
            # A second hand-written copy is how this log came to announce "policy rules
            # (registry holds zero rules)" long after the policy pre-flight existed and
            # rules were no longer the missing piece - an approved policy document was.
            # The list already told callers to consult /api/v1/meta as authoritative;
            # now it cannot disagree with it.
            "capabilities": list(UNIMPLEMENTED_CAPABILITIES),
            "detail": "See GET /api/v1/meta for the authoritative list.",
        },
    )
    worker_task: asyncio.Task[None] | None = None
    worker_stop: asyncio.Event | None = None
    if not settings.is_test:
        extractor = build_receipt_extractor(settings)
        storage = build_receipt_storage(settings)
        app.state.receipt_extractor = extractor
        app.state.receipt_storage = storage
        worker_stop = asyncio.Event()
        worker = ExtractionJobWorker(
            session_factory=get_session_factory(),
            storage=storage,
            extractor=extractor,
            concurrency=settings.extraction_concurrency,
            max_attempts=settings.extraction_max_attempts,
            timeout_seconds=settings.extraction_timeout_seconds,
            retry_backoff_seconds=settings.extraction_retry_backoff_seconds,
        )
        worker_task = asyncio.create_task(
            worker.run(worker_stop), name="proofline-extraction-worker"
        )
    try:
        yield
    finally:
        if worker_stop is not None:
            worker_stop.set()
        if worker_task is not None:
            await worker_task
        active_extractor = getattr(app.state, "receipt_extractor", None)
        if active_extractor is not None and hasattr(active_extractor, "close"):
            active_extractor.close()
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
            "creation, private receipt upload, claim correction/submission and human review "
            "decisions. Raw OCR/model text is not retained. Production authentication, policy "
            "evaluation and approval task workflows remain incomplete. "
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
