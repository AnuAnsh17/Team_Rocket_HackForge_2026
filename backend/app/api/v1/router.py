"""v1 route aggregation.

Built by a function rather than a module-level singleton on purpose. FastAPI wraps
``include_router`` contributions in a nested router object, so a module-level
singleton would bake the demo-mode decision in at import time and make the
"demo routes are absent when demo mode is off" behaviour untestable. Building the
router inside ``create_app`` keeps that decision where it belongs.
"""

from fastapi import APIRouter

from app.api.v1.routes import (
    analytics,
    expense_lifecycle,
    expenses,
    health,
    identity,
    meta,
    receipts,
)
from app.core.config import settings


def build_api_router(*, demo_mode: bool | None = None) -> APIRouter:
    """Assemble the v1 router.

    Only the routes included here are part of the served contract. Everything else
    described in docs/api-contract.md is reported by ``/api/v1/meta`` as an
    unimplemented capability, so a caller is never left guessing which endpoints
    exist.

    The demo router is included only when demo mode is genuinely enabled, so when it
    is off the paths are absent and answer 404 - which does not disclose that a
    disabled demo surface exists.
    """
    enabled = settings.demo_routes_enabled if demo_mode is None else demo_mode

    router = APIRouter()
    router.include_router(health.router)
    router.include_router(meta.router)
    router.include_router(identity.router)
    router.include_router(expense_lifecycle.router)
    router.include_router(analytics.router)
    router.include_router(expenses.router)
    router.include_router(receipts.router)

    if enabled:
        from app.api.v1.routes import demo

        router.include_router(demo.router)

    return router


__all__ = ["build_api_router"]
