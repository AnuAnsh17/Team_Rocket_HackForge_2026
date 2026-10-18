"""Verification tests for the Supabase access-token provider.

These tests are not fixtures pretending to be Supabase. They generate a real RSA key pair,
serve a real JWKS document over a stubbed HTTP transport, and sign real JWTs with the
private half. Every accepted token is verified by the production code path
(``jwt.decode`` with a pinned algorithm allowlist, issuer, audience and expiry), and every
rejected token is rejected by that same code - not by a test double.

What is stubbed: only the JWKS *transport*, so the suite needs no network. The fetching,
parsing, key selection, caching and rotation behaviour around it are the real
implementations and are asserted here.

The second half of the file covers the other half of the boundary: a *verified* identity
must still be joined to a pre-provisioned Proofline user and an active membership, and must
never be able to authenticate as somebody else or provision itself.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import pytest
from app.api.deps import get_identity
from app.core.config import Settings
from app.core.enums import MembershipStatus, RoleCode
from app.core.errors import Unauthenticated
from app.core.security import JwksCache, SupabaseAuthProvider
from app.models.identity import OrganizationMembership, RoleAssignment, User
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import Request
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from sqlalchemy.orm import Session

ISSUER = "https://project-ref.supabase.co/auth/v1"
AUDIENCE = "authenticated"
JWKS_URL = "https://project-ref.supabase.co/auth/v1/.well-known/jwks.json"
KEY_ID = "proofline-test-key"


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    """A real RSA key pair, generated for this module."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(private_key: rsa.RSAPrivateKey, key_id: str = KEY_ID) -> dict[str, Any]:
    jwk: dict[str, Any] = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": key_id, "alg": "RS256", "use": "sig"})
    return jwk


class KeySetServer:
    """A stubbed JWKS endpoint that counts fetches and can rotate keys or fail."""

    def __init__(self, keys: list[dict[str, Any]] | None = None) -> None:
        self.keys: list[dict[str, Any]] = list(keys or [])
        self.fetches = 0
        self.fail_status: int | None = None

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.fetches += 1
        if self.fail_status is not None:
            return httpx.Response(self.fail_status, json={"error": "unavailable"})
        return httpx.Response(200, json={"keys": self.keys})


@pytest.fixture
def key_server(signing_key: rsa.RSAPrivateKey) -> KeySetServer:
    return KeySetServer([_jwk(signing_key)])


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "_env_file": None,
        "APP_ENV": "test",
        "AUTH_PROVIDER": "supabase",
        "SUPABASE_JWT_ISSUER": ISSUER,
        "SUPABASE_JWT_AUDIENCE": AUDIENCE,
        "SUPABASE_JWKS_URL": JWKS_URL,
        "DEMO_MODE": False,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _provider(server: KeySetServer, **overrides: Any) -> SupabaseAuthProvider:
    cache = JwksCache(JWKS_URL, client=httpx.Client(transport=server.transport()))
    return SupabaseAuthProvider(_settings(**overrides), jwks=cache)


def _request(**headers: str) -> Request:
    raw = [(name.lower().encode("ascii"), value.encode("ascii")) for name, value in headers.items()]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/me",
            "raw_path": b"/api/v1/me",
            "query_string": b"",
            "headers": raw,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


def _token(
    private_key: rsa.RSAPrivateKey,
    *,
    subject: str = "5f0f4c2e-0000-4000-8000-0000000000ab",
    key_id: str | None = KEY_ID,
    algorithm: str = "RS256",
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    expires_in: int = 3600,
    not_before: int | None = None,
    signing_key: rsa.RSAPrivateKey | None = None,
    **extra: Any,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "email": "reviewer@example.test",
        "role": "authenticated",
        "session_id": str(uuid.uuid4()),
    }
    if not_before is not None:
        payload["nbf"] = now + timedelta(seconds=not_before)
    payload.update(extra)
    headers = {"kid": key_id} if key_id else {}
    return jwt.encode(payload, signing_key or private_key, algorithm=algorithm, headers=headers)


def _unsigned_token(payload: dict[str, Any], key_id: str = KEY_ID) -> str:
    """A token with ``alg: none`` and an empty signature - the classic bypass attempt."""

    def segment(value: dict[str, Any]) -> str:
        encoded = base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode())
        return encoded.rstrip(b"=").decode("ascii")

    header = {"alg": "none", "typ": "JWT", "kid": key_id}
    return f"{segment(header)}.{segment(payload)}."


class TestValidTokensAreAccepted:
    def test_a_signed_token_resolves_to_its_subject(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        subject = str(uuid.uuid4())
        token = _token(signing_key, subject=subject)

        identity = _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

        assert identity.subject == subject
        assert identity.provider == "supabase"
        assert identity.email == "reviewer@example.test"
        # Only an allowlist of claims is carried forward; the token itself is not retained.
        assert "session_id" in identity.claims
        assert token not in json.dumps(identity.claims)

    def test_the_bearer_scheme_is_case_insensitive_and_surrounding_space_is_tolerated(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        token = _token(signing_key)
        identity = _provider(key_server).resolve_identity(
            _request(Authorization=f"  bearer   {token}  ")
        )
        assert identity.subject

    def test_the_key_set_is_fetched_once_and_then_served_from_cache(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        provider = _provider(key_server)
        token = _token(signing_key)

        for _ in range(3):
            provider.resolve_identity(_request(Authorization=f"Bearer {token}"))

        # Verification runs on every request; refetching the key set each time would add a
        # network round trip to every call and let an anonymous caller drive that traffic.
        assert key_server.fetches == 1

    def test_a_rotated_key_is_picked_up_and_an_unknown_key_id_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        first = _provider(key_server)
        first.resolve_identity(_request(Authorization=f"Bearer {_token(signing_key)}"))
        assert key_server.fetches == 1

        rotated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_server.keys = [_jwk(rotated, "rotated-key")]

        with pytest.raises(Unauthenticated):
            first.resolve_identity(
                _request(Authorization=f"Bearer {_token(signing_key, key_id='rotated-key')}")
            )
        # The unknown key id triggered a refresh, which is how a rotation is picked up.
        assert key_server.fetches == 2

        identity = first.resolve_identity(
            _request(Authorization=f"Bearer {_token(rotated, key_id='rotated-key')}")
        )
        assert identity.subject

        with pytest.raises(Unauthenticated, match="does not recognise"):
            first.resolve_identity(
                _request(Authorization=f"Bearer {_token(rotated, key_id='never-published')}")
            )


class TestTokensThatMustBeRefused:
    def test_a_missing_or_malformed_authorization_header_is_refused(
        self, key_server: KeySetServer
    ) -> None:
        provider = _provider(key_server)
        for headers in (
            {},
            {"Authorization": ""},
            {"Authorization": "Basic dXNlcjpwYXNz"},
            {"Authorization": "Bearer"},
            {"Authorization": "Bearer    "},
        ):
            with pytest.raises(Unauthenticated):
                provider.resolve_identity(_request(**headers))

    def test_a_token_that_is_not_a_jwt_is_refused(self, key_server: KeySetServer) -> None:
        with pytest.raises(Unauthenticated, match="well-formed"):
            _provider(key_server).resolve_identity(_request(Authorization="Bearer not-a-jwt"))

    def test_an_expired_token_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        token = _token(signing_key, expires_in=-3600)
        with pytest.raises(Unauthenticated, match="expired"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_a_token_that_is_not_valid_yet_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        token = _token(signing_key, not_before=3600)
        with pytest.raises(Unauthenticated, match="not valid yet"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_the_configured_clock_skew_is_bounded(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        just_expired = _token(signing_key, expires_in=-10)
        identity = _provider(key_server).resolve_identity(
            _request(Authorization=f"Bearer {just_expired}")
        )
        assert identity.subject  # inside the 30-second allowance

        long_expired = _token(signing_key, expires_in=-600)
        with pytest.raises(Unauthenticated, match="expired"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {long_expired}"))

    def test_a_token_for_another_issuer_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        token = _token(signing_key, issuer="https://attacker.example/auth/v1")
        with pytest.raises(Unauthenticated, match="another issuer"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_a_token_for_another_audience_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        token = _token(signing_key, audience="some-other-service")
        with pytest.raises(Unauthenticated, match="another audience"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_a_token_signed_by_an_untrusted_key_with_a_trusted_key_id_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        """The attacker knows the published ``kid`` but not the private key."""
        attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _token(attacker, key_id=KEY_ID)

        with pytest.raises(Unauthenticated, match="could not be verified"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_a_tampered_payload_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        token = _token(signing_key, subject="original-subject")
        header, payload, signature = token.split(".")
        # Re-encode the payload with a different subject, keeping the original signature.
        forged = json.loads(base64.urlsafe_b64decode(payload + "==").decode("utf-8"))
        forged["sub"] = str(uuid.uuid4())
        re_encoded = (
            base64.urlsafe_b64encode(json.dumps(forged, separators=(",", ":")).encode())
            .rstrip(b"=")
            .decode("ascii")
        )
        tampered = f"{header}.{re_encoded}.{signature}"

        with pytest.raises(Unauthenticated, match="could not be verified"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {tampered}"))

    def test_an_unsigned_alg_none_token_is_refused(self, key_server: KeySetServer) -> None:
        token = _unsigned_token({"sub": str(uuid.uuid4()), "iss": ISSUER, "aud": AUDIENCE})
        with pytest.raises(Unauthenticated, match="signing algorithm"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_an_hmac_token_signed_with_the_public_key_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        """The key-confusion attack: HMAC-sign with the published public key as the secret.

        Built by hand because PyJWT refuses to produce this token at all (it will not use an
        asymmetric key as an HMAC secret) - so the token is constructed the way an attacker
        would, and the service still has to refuse it.
        """
        public_pem = signing_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        )
        now = int(datetime.now(UTC).timestamp())

        def segment(value: dict[str, Any]) -> str:
            encoded = base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode())
            return encoded.rstrip(b"=").decode("ascii")

        header = {"alg": "HS256", "typ": "JWT", "kid": KEY_ID}
        payload = {
            "sub": str(uuid.uuid4()),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + 3600,
        }
        signing_input = f"{segment(header)}.{segment(payload)}".encode("ascii")
        signature = hmac.new(public_pem, signing_input, hashlib.sha256).digest()
        token = f"{signing_input.decode('ascii')}."
        token += base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")

        with pytest.raises(Unauthenticated, match="signing algorithm"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_a_token_without_a_key_id_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        token = _token(signing_key, key_id=None)
        with pytest.raises(Unauthenticated, match="does not identify its signing key"):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_a_token_without_a_subject_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        token = _token(signing_key, sub="")
        with pytest.raises(Unauthenticated):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_a_token_missing_a_required_claim_is_refused(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        payload = {"sub": str(uuid.uuid4()), "iss": ISSUER, "aud": AUDIENCE}
        token = jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": KEY_ID})
        with pytest.raises(Unauthenticated):
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

    def test_a_refusal_never_echoes_the_token_or_a_verification_oracle(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _token(attacker)

        with pytest.raises(Unauthenticated) as failure:
            _provider(key_server).resolve_identity(_request(Authorization=f"Bearer {token}"))

        message = str(failure.value)
        assert token not in message
        assert "signature" not in message.lower()

    def test_a_key_set_that_cannot_be_fetched_fails_closed(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        key_server.fail_status = 503
        with pytest.raises(Unauthenticated, match="could not be retrieved"):
            _provider(key_server).resolve_identity(
                _request(Authorization=f"Bearer {_token(signing_key)}")
            )

    def test_a_key_set_with_no_usable_keys_fails_closed(
        self, signing_key: rsa.RSAPrivateKey
    ) -> None:
        empty = KeySetServer([])
        with pytest.raises(Unauthenticated, match="no usable signing keys"):
            _provider(empty).resolve_identity(
                _request(Authorization=f"Bearer {_token(signing_key)}")
            )


class TestConfigurationFailsClosed:
    def test_selecting_supabase_without_an_issuer_is_refused_at_startup(self) -> None:
        with pytest.raises(ValueError, match="required configuration is missing"):
            _settings(SUPABASE_JWT_ISSUER=None)

    def test_selecting_supabase_without_a_key_set_is_refused_at_startup(self) -> None:
        with pytest.raises(ValueError, match="required configuration is missing"):
            _settings(SUPABASE_JWKS_URL=None)

    def test_the_provider_itself_refuses_to_start_without_an_issuer_or_key_set(self) -> None:
        """Defence in depth for a config object assembled without validation."""
        without_issuer = Settings.model_construct(
            auth_provider="supabase",
            supabase_jwt_issuer=None,
            supabase_jwks_url=JWKS_URL,
            supabase_jwt_algorithms="RS256",
            supabase_jwt_leeway_seconds=30,
        )
        with pytest.raises(RuntimeError, match="SUPABASE_JWT_ISSUER"):
            SupabaseAuthProvider(without_issuer)

        without_keys = Settings.model_construct(
            auth_provider="supabase",
            supabase_jwt_issuer=ISSUER,
            supabase_jwks_url=None,
            supabase_jwt_algorithms="RS256",
            supabase_jwt_leeway_seconds=30,
        )
        with pytest.raises(RuntimeError, match="SUPABASE_JWKS_URL"):
            SupabaseAuthProvider(without_keys)

    @pytest.mark.parametrize("algorithms", ["", "   ", "none", "NONE", "HS256", "RS256,HS512"])
    def test_an_unsigned_or_hmac_algorithm_allowlist_is_refused(self, algorithms: str) -> None:
        with pytest.raises(ValueError, match="SUPABASE_JWT_ALGORITHMS"):
            _settings(SUPABASE_JWT_ALGORITHMS=algorithms)

    def test_a_comma_separated_allowlist_is_parsed_rather_than_rejected(self) -> None:
        # Guards the pydantic-settings list-decoding trap that CORS_ALLOWED_ORIGINS hits.
        config = _settings(SUPABASE_JWT_ALGORITHMS="RS256, ES256")
        assert config.supabase_jwt_algorithm_set == ("RS256", "ES256")

    def test_the_configured_allowlist_is_what_the_provider_enforces(
        self, key_server: KeySetServer, signing_key: rsa.RSAPrivateKey
    ) -> None:
        provider = _provider(key_server, SUPABASE_JWT_ALGORITHMS="RS512")
        with pytest.raises(Unauthenticated, match="signing algorithm"):
            provider.resolve_identity(_request(Authorization=f"Bearer {_token(signing_key)}"))


def _provision_supabase_actor(
    db: Session, subject: str, *, status: str = MembershipStatus.ACTIVE.value
) -> uuid.UUID:
    """Provision a Supabase-authenticated user with a membership, as an admin would."""
    from app.services import demo_service

    organization = demo_service._ensure_organization(db)
    user = User(
        display_name="Supabase provisioned reviewer",
        email="reviewer@example.test",
        external_subject=subject,
        auth_provider="supabase",
        is_active=True,
        primary_organization_id=organization.id,
    )
    db.add(user)
    db.flush()
    membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user.id,
        status=status,
        is_primary=True,
    )
    db.add(membership)
    db.flush()
    db.add(
        RoleAssignment(
            organization_id=organization.id,
            membership_id=membership.id,
            role=RoleCode.FINANCE_REVIEWER.value,
            # Organization scope keeps the uniqueness constraint meaningful; scope_id is
            # always populated and equals the organization id at this scope.
            scope_type="organization",
            scope_id=organization.id,
            reason="provisioned for the Supabase verification tests",
        )
    )
    db.commit()
    return user.id


class TestVerifiedIdentityIsStillAuthorizedByTheDatabase:
    """A valid Supabase token proves *who* the caller is. It grants nothing by itself."""

    @pytest.fixture
    def supabase_client(self, client: TestClient, key_server: KeySetServer) -> Iterator[TestClient]:
        """The real app, with identity resolution switched to the Supabase provider."""
        provider = _provider(key_server)
        client.app.dependency_overrides[get_identity] = provider.resolve_identity  # type: ignore[attr-defined]
        yield client

    def test_a_verified_token_becomes_an_actor_with_database_permissions(
        self,
        supabase_client: TestClient,
        db: Session,
        seeded: dict[str, object],
        key_server: KeySetServer,
        signing_key: rsa.RSAPrivateKey,
    ) -> None:
        subject = str(uuid.uuid4())
        user_id = _provision_supabase_actor(db, subject)
        token = _token(signing_key, subject=subject)

        response = supabase_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200, response.text
        body = response.json()
        # The verified token's subject was joined to the provisioned user and its active
        # membership, and the response carries the membership the database holds.
        assert body["user"]["id"] == str(user_id)
        assert body["status"] == "active"
        assert body["user"]["display_name"] == "Supabase provisioned reviewer"

        # Roles and permissions come from the Proofline database, not from the token: the
        # provisioned finance_reviewer grant is what allows organization-wide analytics,
        # and the employee-level drilldown it does not hold is still refused.
        overview = supabase_client.get(
            "/api/v1/analytics/overview",
            params={"from": "2026-01-01", "to": "2026-12-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert overview.status_code == 200, overview.text

        drilldown = supabase_client.get(
            "/api/v1/analytics/spend",
            params={"from": "2026-01-01", "to": "2026-12-31", "group_by": "employee"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert drilldown.status_code == 403

    def test_a_verified_token_for_an_unprovisioned_subject_is_refused(
        self,
        supabase_client: TestClient,
        seeded: dict[str, object],
        key_server: KeySetServer,
        signing_key: rsa.RSAPrivateKey,
    ) -> None:
        """No just-in-time provisioning: an unknown subject has no user and no membership."""
        token = _token(signing_key, subject=str(uuid.uuid4()))

        response = supabase_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401

    def test_a_verified_identity_without_an_active_membership_is_refused(
        self,
        supabase_client: TestClient,
        db: Session,
        seeded: dict[str, object],
        key_server: KeySetServer,
        signing_key: rsa.RSAPrivateKey,
    ) -> None:
        subject = str(uuid.uuid4())
        _provision_supabase_actor(db, subject, status=MembershipStatus.TERMINATED.value)
        token = _token(signing_key, subject=subject)

        response = supabase_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

        # A valid identity with no active membership is 403, not 401: we know who they are.
        assert response.status_code == 403

    def test_the_demo_actor_header_cannot_authenticate_when_supabase_is_selected(
        self,
        supabase_client: TestClient,
        seeded: dict[str, object],
    ) -> None:
        """The demo switcher must be inert outside demo mode, even if a client sends it."""
        subjects = seeded["subjects"]
        assert isinstance(subjects, dict)

        response = supabase_client.get(
            "/api/v1/me",
            headers={
                "X-Demo-Actor-Id": str(subjects["finance.admin"]),
                "X-Demo-Organization-Id": "00000000-0000-4000-8000-000000000001",
            },
        )

        assert response.status_code == 401

    def test_a_token_that_fails_verification_never_reaches_the_actor_resolver(
        self,
        supabase_client: TestClient,
        db: Session,
        seeded: dict[str, object],
        key_server: KeySetServer,
        signing_key: rsa.RSAPrivateKey,
    ) -> None:
        subject = str(uuid.uuid4())
        _provision_supabase_actor(db, subject)
        expired = _token(signing_key, subject=subject, expires_in=-3600)

        response = supabase_client.get("/api/v1/me", headers={"Authorization": f"Bearer {expired}"})

        assert response.status_code == 401
