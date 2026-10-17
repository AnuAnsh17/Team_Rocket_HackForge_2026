"""Authentication boundary: identity in, actor out.

The separation matters. A client supplies a *credential*; the backend derives an
*identity* from it; the backend then loads the actor's authoritative membership,
roles and permissions from its own database. A client can never assert a role,
employee id, department, grade, allowance or approval limit.

Three providers exist:

  ``DemoAuthProvider``        reads X-Demo-Actor-Id. Active ONLY when
                              DEMO_MODE=true and APP_ENV is not production
                              (both enforced by config validation). Fails closed.
  ``SupabaseAuthProvider``    validates a real Supabase-issued JWT against the
                              project's JWKS. NOT IMPLEMENTED in this scaffold:
                              it raises NotImplementedYet rather than accepting
                              an unverified token.
  ``NoAuthProvider``          accepts nothing. Used in tests that assert
                              fail-closed behaviour.

The interface is intentionally narrow so a different identity provider can be
introduced without touching any expense or policy service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from fastapi import Request

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.core.enums import AuditActorType, RoleCode
from app.core.errors import Forbidden, NotImplementedYet, Unauthenticated
from app.core.permissions import Permission

DEMO_ACTOR_HEADER = "x-demo-actor-id"
DEMO_ORGANIZATION_HEADER = "x-demo-organization-id"


@dataclass(frozen=True, slots=True)
class Identity:
    """A verified or demo-attributed external identity. Not yet authorized."""

    subject: str
    provider: str
    email: str | None = None
    claims: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MembershipContext:
    """One organization membership with its organization-scoped roles."""

    membership_id: str
    organization_id: str
    roles: frozenset[RoleCode]


@dataclass(frozen=True, slots=True)
class Actor:
    """An authenticated identity joined to its authoritative server-side data."""

    user_id: str
    identity: Identity
    memberships: tuple[MembershipContext, ...]
    active_organization_id: str | None
    active_membership_id: str | None
    roles: frozenset[RoleCode]
    permissions: frozenset[Permission]
    actor_type: AuditActorType

    @property
    def is_demo(self) -> bool:
        return self.actor_type == AuditActorType.DEMO

    def require(self, permission: Permission) -> None:
        """Raise Forbidden unless the actor holds the permission.

        This is the coarse gate only. Callers must additionally apply a
        resource-level scope check; see app/services/scope_service.py.
        """
        if permission not in self.permissions:
            raise Forbidden(
                f"Missing required permission: {permission.value}",
                details=[{"required_permission": permission.value}],
            )

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions


@runtime_checkable
class AuthProvider(Protocol):
    """Exchange a request for a verified identity, or refuse."""

    name: str

    def resolve_identity(self, request: Request) -> Identity:
        """Return a verified identity or raise Unauthenticated."""
        ...


class NoAuthProvider:
    """Refuses every request. The safe default for fail-closed tests."""

    name = "disabled"

    def resolve_identity(self, request: Request) -> Identity:
        raise Unauthenticated("Authentication is disabled in this configuration.")


class DemoAuthProvider:
    """Demo-only identity provider.

    Reads X-Demo-Actor-Id (a seeded user's uuid) from the request. It is
    constructed only when demo mode is enabled outside production, and it never
    invents roles: the referenced user's roles come from the database like any
    other actor's.
    """

    name = "demo"

    def __init__(self, config: Settings | None = None) -> None:
        config = config or default_settings
        if not config.demo_routes_enabled:
            raise RuntimeError(
                "DemoAuthProvider must not be constructed unless DEMO_MODE is true "
                "and APP_ENV is not production."
            )

    def resolve_identity(self, request: Request) -> Identity:
        actor_id = request.headers.get(DEMO_ACTOR_HEADER)
        if not actor_id:
            raise Unauthenticated(
                "Demo mode requires the X-Demo-Actor-Id header. "
                "Demo mode never falls back to a default identity."
            )
        return Identity(
            subject=actor_id.strip(),
            provider=self.name,
            email=None,
            claims={"demo": True},
        )


class SupabaseAuthProvider:
    """Real Supabase JWT validation. NOT IMPLEMENTED in this scaffold.

    The intended implementation is documented in docs/authentication-security.md:

      1. Read the bearer token from the Authorization header.
      2. Fetch and cache the project JWKS from SUPABASE_JWKS_URL.
      3. Verify the signature, ``iss`` (SUPABASE_JWT_ISSUER), ``aud``
         (SUPABASE_JWT_AUDIENCE) and ``exp``/``nbf`` with a small clock skew.
      4. Return an Identity carrying ``sub`` (the Supabase user id).
      5. Resolve membership, roles and permissions from the Proofline database.

    Until that is implemented and security-tested, this provider refuses every
    request. It must not be replaced with an unverified base64 decode.
    """

    name = "supabase"

    def __init__(self, config: Settings | None = None) -> None:
        self._config = config or default_settings

    def resolve_identity(self, request: Request) -> Identity:
        raise NotImplementedYet(
            "Supabase JWT validation is not implemented in the scaffolding phase. "
            "No token is trusted until signature, issuer, audience and expiry "
            "validation is implemented and security-tested."
        )


def build_auth_provider(config: Settings | None = None) -> AuthProvider:
    """Select the configured provider. Demo mode can never be selected in production."""
    config = config or default_settings
    if config.auth_provider == "demo":
        if not config.demo_routes_enabled:
            # Defence in depth: config validation should already have refused this.
            return NoAuthProvider()
        return DemoAuthProvider(config)
    if config.auth_provider == "supabase":
        return SupabaseAuthProvider(config)
    return NoAuthProvider()
