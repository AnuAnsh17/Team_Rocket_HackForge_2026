"""FastAPI dependency wiring.

Every dependency here is a seam that keeps a cross-cutting concern in exactly one
place: one session lifecycle, one authentication boundary, one permission check,
one pagination parser.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import suppress
from threading import Lock

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.config import settings as app_settings
from app.core.errors import Forbidden, NotImplementedYet
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, Pagination, decode_cursor
from app.core.permissions import Permission
from app.core.security import Actor, Identity, build_auth_provider
from app.db.session import get_session_factory
from app.extraction.base import ReceiptExtractor
from app.extraction.factory import build_receipt_extractor
from app.services.actor_service import resolve_actor
from app.storage.base import ReceiptStorage
from app.storage.factory import build_receipt_storage

AUTH_PROVIDER_HEADER = "x-demo-organization-id"
_EXTRACTOR_INIT_LOCK = Lock()


def get_settings_dep() -> Settings:
    """Expose settings to routes without importing the module singleton directly."""
    return app_settings


def get_receipt_extractor(request: Request) -> ReceiptExtractor:
    """Build one app-scoped extractor so a local OCR model stays warm per worker."""
    extractor = getattr(request.app.state, "receipt_extractor", None)
    if extractor is None:
        with _EXTRACTOR_INIT_LOCK:
            extractor = getattr(request.app.state, "receipt_extractor", None)
            if extractor is None:
                extractor = build_receipt_extractor(app_settings)
                request.app.state.receipt_extractor = extractor
    return extractor


def get_receipt_storage(request: Request) -> ReceiptStorage:
    """Build one app-scoped storage adapter."""
    storage = getattr(request.app.state, "receipt_storage", None)
    if storage is None:
        storage = build_receipt_storage(app_settings)
        request.app.state.receipt_storage = storage
    return storage


def get_session(request: Request) -> Iterator[Session]:
    """One database session per request, committed on success.

    The route does not commit. If the handler returns normally the session is
    committed; if it raises, the whole transaction - including any audit event it
    appended - is rolled back. That is what makes "a state change and its audit
    event are atomic" a property of the framework wiring rather than a promise each
    route has to keep.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        callbacks = getattr(request.state, "rollback_callbacks", [])
        request.state.rollback_callbacks = []
        for callback in callbacks:
            with suppress(Exception):
                callback()
        raise
    else:
        # A successful commit makes the stored object part of the committed
        # receipt record; discard rollback-only cleanup callbacks.
        request.state.rollback_callbacks = []
    finally:
        session.close()


def get_identity(request: Request) -> Identity:
    """Resolve and verify the caller's external identity."""
    provider = build_auth_provider(app_settings)
    return provider.resolve_identity(request)


def get_actor(
    request: Request,
    session: Session = Depends(get_session),
    identity: Identity = Depends(get_identity),
) -> Actor:
    """Resolve the authenticated actor with authoritative roles and permissions.

    Note what is read from the request: only an optional organization hint. No
    role, employee id, department, grade, allowance or approval limit is ever
    accepted from the client.
    """
    return resolve_actor(
        session,
        identity,
        requested_organization_id=request.headers.get(AUTH_PROVIDER_HEADER),
    )


def require(permission: Permission) -> Callable[..., Actor]:
    """Build a dependency asserting one permission.

    Coarse gate only: routes that act on a specific record must additionally call
    the matching function in app/services/scope_service.py, which enforces
    organization and relationship scope.
    """

    def _dependency(actor: Actor = Depends(get_actor)) -> Actor:
        actor.require(permission)
        return actor

    return _dependency


def require_demo_mode() -> None:
    """Refuse demo-only routes unless demo mode is genuinely enabled.

    When demo mode is off, the demo router is not even registered, so this is
    defence in depth for the case where a router is mounted by a future change.
    """
    if not app_settings.demo_routes_enabled:
        raise Forbidden("Demo utilities are not enabled in this environment.")


def get_pagination(
    limit: int = Query(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description="Maximum number of items to return.",
    ),
    cursor: str | None = Query(
        default=None,
        description="Opaque cursor from the previous page's page.next_cursor.",
    ),
) -> Pagination:
    """Parse the documented pagination inputs into a validated object."""
    offset = decode_cursor(cursor) if cursor else 0
    return Pagination(limit=limit, offset=offset, cursor=cursor)


def not_implemented(capability: str) -> Callable[..., None]:
    """Raise a 501 that names the capability instead of failing silently."""

    def _raise() -> None:
        raise NotImplementedYet(f"{capability} is not implemented in the current scaffold.")

    return _raise
