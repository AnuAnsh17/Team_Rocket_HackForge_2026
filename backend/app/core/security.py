"""Authentication boundary: identity in, actor out.

The separation matters. A client supplies a *credential*; the backend derives an
*identity* from it; the backend then loads the actor's authoritative membership,
roles and permissions from its own database. A client can never assert a role,
employee id, department, grade, allowance or approval limit.

Three providers exist:

  ``DemoAuthProvider``        reads X-Demo-Actor-Id. Active ONLY when
                              DEMO_MODE=true and APP_ENV is not production
                              (both enforced by config validation). Fails closed.
  ``SupabaseAuthProvider``    verifies a real Supabase-issued JWT against the
                              project's JWKS, then lets the actor resolver join
                              the verified ``sub`` to a pre-provisioned user and
                              membership. It never creates a membership.
  ``NoAuthProvider``          accepts nothing. Used in tests that assert
                              fail-closed behaviour.

The interface is intentionally narrow so a different identity provider can be
introduced without touching any expense or policy service.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx
import jwt
from fastapi import Request

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.core.enums import AuditActorType, RoleCode
from app.core.errors import Forbidden, Unauthenticated
from app.core.permissions import Permission

DEMO_ACTOR_HEADER = "x-demo-actor-id"
DEMO_ORGANIZATION_HEADER = "x-demo-organization-id"
AUTHORIZATION_HEADER = "authorization"
BEARER_SCHEME = "bearer"

# Claims carried onto the Identity. An allowlist rather than the whole payload: the token
# is never retained, and nothing is copied forward that no downstream reader needs.
_IDENTITY_CLAIMS = ("aud", "iss", "exp", "iat", "role", "email", "sub", "session_id")


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


class JwksCache:
    """Fetches and caches the project's JSON Web Key Set, keyed by ``kid``.

    Cached because verification happens on every request: fetching the key set per request
    would add a network round trip to each call and let an unauthenticated caller drive
    traffic to the identity provider.

    The URL is not secret - a JWKS is public by design - and nothing here is logged beyond
    counts, so no token or key material reaches a log line.
    """

    def __init__(
        self,
        url: str,
        *,
        ttl_seconds: float = 300.0,
        timeout_seconds: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not url:
            raise ValueError("A JWKS URL is required to verify access tokens.")
        self._url = url
        self._ttl_seconds = ttl_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._lock = threading.Lock()
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at = 0.0
        # Counters for observability without exposing anything sensitive.
        self.refresh_count = 0

    def _is_stale(self) -> bool:
        return (time.monotonic() - self._fetched_at) >= self._ttl_seconds

    def get(self, key_id: str) -> dict[str, Any] | None:
        """Return the JWK for ``key_id``, refreshing once when it is unknown or stale."""
        with self._lock:
            cached = self._keys.get(key_id)
            if cached is not None and not self._is_stale():
                return cached
            # An unknown key id is normal for a short window after the project rotates its
            # signing key, so a stale cache is refreshed at most once per call here.
            self._refresh_locked()
            return self._keys.get(key_id)

    def _refresh_locked(self) -> None:
        try:
            response = self._client.get(self._url, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload: Any = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise Unauthenticated(
                "The identity provider's signing keys could not be retrieved, so the "
                "access token cannot be verified."
            ) from exc

        keys = payload.get("keys") if isinstance(payload, dict) else None
        if not isinstance(keys, list):
            raise Unauthenticated(
                "The identity provider returned a key set this service cannot read."
            )

        parsed: dict[str, dict[str, Any]] = {}
        for key in keys:
            if not isinstance(key, dict):
                continue
            key_id = key.get("kid")
            if isinstance(key_id, str) and key_id:
                parsed[key_id] = key

        if not parsed:
            raise Unauthenticated("The identity provider returned no usable signing keys.")

        self._keys = parsed
        self._fetched_at = time.monotonic()
        self.refresh_count += 1


# One cache per JWKS URL, process-wide.
#
# ``build_auth_provider`` runs per request (see app/api/deps.py::get_identity), so a cache
# owned by the provider instance would be discarded before it could ever be used and every
# request would refetch the key set.
_JWKS_CACHES: dict[str, JwksCache] = {}
_JWKS_CACHES_LOCK = threading.Lock()


def shared_jwks_cache(url: str) -> JwksCache:
    """Return the process-wide cache for ``url``, creating it on first use."""
    with _JWKS_CACHES_LOCK:
        cache = _JWKS_CACHES.get(url)
        if cache is None:
            cache = JwksCache(url)
            _JWKS_CACHES[url] = cache
        return cache


class SupabaseAuthProvider:
    """Verifies a Supabase-issued access token, then trusts only its ``sub``.

    Implemented per docs/authentication-security.md:

      1. Read the bearer token from the ``Authorization`` header.
      2. Fetch and cache the project's JWKS from ``SUPABASE_JWKS_URL``.
      3. Verify the signature and validate ``iss``, ``aud`` and ``exp``/``nbf`` with a
         small bounded clock skew, accepting only algorithms on the configured allowlist
         (asymmetric only, so an unsigned or HMAC-signed token is refused).
      4. Accept the token's ``sub`` as the external identity.

    What this provider does NOT do is decide authority. It returns an Identity; roles and
    membership come from the Proofline database via
    ``app/services/actor_service.py::resolve_actor``, which refuses a subject with no
    provisioned user (401) or no active membership (403). A valid Supabase token therefore
    never grants access on its own, and no membership is ever created implicitly.
    """

    name = "supabase"

    def __init__(self, config: Settings | None = None, *, jwks: JwksCache | None = None) -> None:
        config = config or default_settings
        if not config.supabase_jwt_issuer:
            raise RuntimeError(
                "SUPABASE_JWT_ISSUER is required to verify access tokens: a token whose "
                "issuer is not checked can be minted by any other project."
            )
        self._config = config
        self._algorithms = config.supabase_jwt_algorithm_set
        self._leeway_seconds = config.supabase_jwt_leeway_seconds
        if jwks is not None:
            self._jwks = jwks
        elif config.supabase_jwks_url:
            self._jwks = shared_jwks_cache(config.supabase_jwks_url)
        else:
            raise RuntimeError("SUPABASE_JWKS_URL is required to verify access tokens.")

    def resolve_identity(self, request: Request) -> Identity:
        token = self._bearer_token(request)
        algorithm, key_id = self._token_header(token)
        jwk = self._jwks.get(key_id)
        if jwk is None:
            raise Unauthenticated(
                "The access token was signed with a key this service does not recognise."
            )

        try:
            signing_key = jwt.PyJWK.from_dict(jwk, algorithm=algorithm)
        except jwt.PyJWTError as exc:
            raise Unauthenticated(
                "The identity provider's signing key is not usable for this token."
            ) from exc

        try:
            claims = jwt.decode(
                token,
                key=signing_key.key,
                algorithms=list(self._algorithms),
                audience=self._config.supabase_jwt_audience,
                issuer=self._config.supabase_jwt_issuer,
                leeway=self._leeway_seconds,
                options={
                    "require": ["exp", "iat", "sub", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise Unauthenticated("The access token has expired.") from exc
        except jwt.ImmatureSignatureError as exc:
            raise Unauthenticated("The access token is not valid yet.") from exc
        except jwt.InvalidAudienceError as exc:
            raise Unauthenticated("The access token was issued for another audience.") from exc
        except jwt.InvalidIssuerError as exc:
            raise Unauthenticated("The access token was issued by another issuer.") from exc
        except jwt.PyJWTError as exc:
            # Signature failures, unsupported algorithms, missing required claims and
            # malformed payloads all land here. The reason is not echoed to the caller:
            # a verification oracle helps an attacker more than it helps a client.
            raise Unauthenticated("The access token could not be verified.") from exc

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise Unauthenticated("The access token carries no usable subject.")

        email = claims.get("email")
        return Identity(
            subject=subject.strip(),
            provider=self.name,
            email=email if isinstance(email, str) else None,
            claims={name: claims[name] for name in _IDENTITY_CLAIMS if name in claims},
        )

    def _bearer_token(self, request: Request) -> str:
        header = request.headers.get(AUTHORIZATION_HEADER, "").strip()
        scheme, _, token = header.partition(" ")
        if scheme.lower() != BEARER_SCHEME or not token.strip():
            raise Unauthenticated("A Bearer access token is required in the Authorization header.")
        return token.strip()

    def _token_header(self, token: str) -> tuple[str, str]:
        """Return the token's ``alg`` and ``kid`` before verification, refusing unknowns.

        The header is read unverified only to choose a key. Nothing in it is trusted: the
        algorithm must be on the allowlist (so ``alg: none`` and HMAC are refused before any
        key is considered) and the signature is still verified against the fetched JWK.
        """
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise Unauthenticated("The access token is not a well-formed JWT.") from exc

        algorithm = header.get("alg")
        if not isinstance(algorithm, str) or algorithm.upper() not in self._algorithms:
            raise Unauthenticated(
                "The access token uses a signing algorithm this service does not accept."
            )
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            raise Unauthenticated("The access token does not identify its signing key.")
        return algorithm.upper(), key_id


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
