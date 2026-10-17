"""Configuration validation. The fail-closed rules are load-bearing."""

from __future__ import annotations

import pytest
from app.core.config import Settings

pytestmark = pytest.mark.unit

PRODUCTION_BASE = {
    "APP_ENV": "production",
    "DEMO_MODE": "false",
    "DATABASE_URL": "postgresql+psycopg://user:secret@db.internal:5432/proofline",
    "RECEIPT_STORAGE_BACKEND": "supabase",
    "AUTH_PROVIDER": "supabase",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_JWT_ISSUER": "https://example.supabase.co/auth/v1",
    "SUPABASE_JWKS_URL": "https://example.supabase.co/auth/v1/.well-known/jwks.json",
}


def _settings(**overrides: str) -> Settings:
    """Build settings from an isolated mapping, ignoring any .env file."""
    values = {**PRODUCTION_BASE, **overrides}
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


class TestFailClosedRules:
    def test_demo_mode_is_refused_in_production(self) -> None:
        with pytest.raises(ValueError, match="DEMO_MODE must be false"):
            _settings(DEMO_MODE="true")

    def test_demo_mode_is_refused_in_staging(self) -> None:
        with pytest.raises(ValueError, match="DEMO_MODE must be false"):
            _settings(APP_ENV="staging", DEMO_MODE="true")

    def test_local_receipt_storage_is_refused_in_production(self) -> None:
        with pytest.raises(ValueError, match="RECEIPT_STORAGE_BACKEND=local"):
            _settings(RECEIPT_STORAGE_BACKEND="local")

    def test_demo_auth_provider_is_refused_in_production(self) -> None:
        # DEMO_MODE must be off first, or the earlier rule fires instead.
        with pytest.raises(ValueError, match="AUTH_PROVIDER=demo"):
            _settings(AUTH_PROVIDER="demo")

    def test_synthetic_policy_is_refused_in_production_and_staging(self) -> None:
        for environment in ("production", "staging"):
            with pytest.raises(ValueError, match="DEMO_SYNTHETIC_POLICY_ENABLED"):
                _settings(APP_ENV=environment, DEMO_SYNTHETIC_POLICY_ENABLED="true")

    def test_development_database_url_is_refused_in_production(self) -> None:
        with pytest.raises(ValueError, match="DATABASE_URL must be set explicitly"):
            _settings(
                DATABASE_URL="postgresql+psycopg://proofline:proofline@localhost:5432/proofline"
            )

    def test_missing_supabase_configuration_is_refused(self) -> None:
        with pytest.raises(ValueError, match="required configuration is missing"):
            _settings(SUPABASE_JWKS_URL="")

    def test_a_valid_production_configuration_is_accepted(self) -> None:
        settings = _settings()
        assert settings.is_production is True
        assert settings.demo_routes_enabled is False


class TestDevelopmentDefaults:
    def test_demo_routes_require_demo_mode(self) -> None:
        settings = Settings(_env_file=None, APP_ENV="development", DEMO_MODE="false")  # type: ignore[arg-type]
        assert settings.demo_routes_enabled is False

    def test_demo_routes_enabled_in_development_with_demo_mode(self) -> None:
        settings = Settings(_env_file=None, APP_ENV="development", DEMO_MODE="true")  # type: ignore[arg-type]
        assert settings.demo_routes_enabled is True

    def test_synthetic_policy_requires_explicit_demo_mode(self) -> None:
        with pytest.raises(ValueError, match="requires DEMO_MODE=true"):
            Settings(
                _env_file=None,
                APP_ENV="development",
                DEMO_MODE="false",
                DEMO_SYNTHETIC_POLICY_ENABLED="true",
            )  # type: ignore[arg-type]

    def test_cors_origins_accept_a_comma_separated_string(self) -> None:
        settings = Settings(  # type: ignore[arg-type]
            _env_file=None,
            APP_ENV="development",
            CORS_ALLOWED_ORIGINS="http://localhost:3000,http://localhost:3001",
        )
        assert settings.cors_allowed_origins == [
            "http://localhost:3000",
            "http://localhost:3001",
        ]


class TestFieldValidation:
    def test_invalid_log_level_is_refused(self) -> None:
        with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
            Settings(_env_file=None, APP_ENV="development", LOG_LEVEL="chatty")  # type: ignore[arg-type]

    def test_negative_upload_limit_is_refused(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            Settings(_env_file=None, APP_ENV="development", RECEIPT_MAX_UPLOAD_BYTES="-1")  # type: ignore[arg-type]

    def test_absurd_upload_limit_is_refused(self) -> None:
        with pytest.raises(ValueError, match="must not exceed"):
            Settings(_env_file=None, APP_ENV="development", RECEIPT_MAX_UPLOAD_BYTES="10485760000")  # type: ignore[arg-type]
