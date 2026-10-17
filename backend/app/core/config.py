"""Central application configuration.

Every environment variable the backend understands is declared here exactly
once and validated at startup. Nothing else in the codebase reads os.environ,
so an unset or contradictory variable fails loudly at boot instead of producing
a confusing runtime error later.

Fail-closed rules enforced below:
  - DEMO_MODE must be false when APP_ENV is production or staging.
  - A real DATABASE_URL is required outside local development and tests.
  - Production must not use the local filesystem receipt backend.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "staging", "production"]

_LOCAL_DATABASE_URL = "postgresql+psycopg://proofline:proofline@localhost:5432/proofline"


class Settings(BaseSettings):
    """Validated application settings."""

    model_config = SettingsConfigDict(
        # Both locations are probed so the same file works whether the process is
        # started from backend/ or from the repository root. Real environment
        # variables always win over either file.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -----------------------------------------------------
    app_env: AppEnv = "development"
    app_name: str = "Proofline API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = True
    demo_mode: bool = False
    demo_synthetic_policy_enabled: bool = False

    # --- Database --------------------------------------------------------
    database_url: str = _LOCAL_DATABASE_URL
    database_pool_size: int = 5
    database_max_overflow: int = 5
    database_echo: bool = False
    database_pool_pre_ping: bool = True

    # --- HTTP ------------------------------------------------------------
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Authentication --------------------------------------------------
    auth_provider: Literal["demo", "supabase", "disabled"] = "demo"
    supabase_url: str | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_url: str | None = None

    # --- Receipt storage -------------------------------------------------
    receipt_storage_backend: Literal["local", "supabase", "s3"] = "local"
    receipt_storage_bucket: str = "receipts-private"
    receipt_local_root: str = ".local-storage/receipts"
    receipt_max_upload_bytes: int = 10 * 1024 * 1024
    receipt_signed_url_ttl_seconds: int = 300

    # --- Extraction ------------------------------------------------------
    extraction_provider: Literal[
        "unavailable",
        "opencode_go",
        "openai_compatible",
        "azure_document_intelligence",
        "local_ocr",
    ] = "unavailable"
    extraction_model: str | None = None
    extraction_timeout_seconds: int = 90
    extraction_python_executable: str | None = None
    extraction_concurrency: int = 2
    extraction_max_attempts: int = 3
    extraction_retry_backoff_seconds: float = 0.5
    opencode_go_api_key: str | None = None
    opencode_go_model: str = "deepseek-v4.1-flash"
    opencode_go_base_url: str = "https://opencode.ai/zen/go/v1"

    # --- Derived ---------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def demo_routes_enabled(self) -> bool:
        """Demo routes exist only when demo mode is on outside production."""
        return self.demo_mode and not self.is_production

    # --- Validators ------------------------------------------------------
    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string as well as a JSON list.

        docker-compose and .env files carry CORS_ALLOWED_ORIGINS as a plain
        comma-separated string; that must not require JSON quoting.
        """
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return value
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}, got {value!r}")
        return upper

    @field_validator("receipt_max_upload_bytes")
    @classmethod
    def _sane_upload_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("RECEIPT_MAX_UPLOAD_BYTES must be positive")
        if value > 100 * 1024 * 1024:
            raise ValueError("RECEIPT_MAX_UPLOAD_BYTES must not exceed 100 MiB")
        return value

    @field_validator("extraction_concurrency")
    @classmethod
    def _sane_extraction_concurrency(cls, value: int) -> int:
        if value < 1 or value > 16:
            raise ValueError("EXTRACTION_CONCURRENCY must be between 1 and 16")
        return value

    @field_validator("extraction_max_attempts")
    @classmethod
    def _sane_extraction_attempts(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("EXTRACTION_MAX_ATTEMPTS must be between 1 and 5")
        return value

    @field_validator("extraction_retry_backoff_seconds")
    @classmethod
    def _sane_extraction_backoff(cls, value: float) -> float:
        if value < 0 or value > 30:
            raise ValueError("EXTRACTION_RETRY_BACKOFF_SECONDS must be between 0 and 30")
        return value

    @model_validator(mode="after")
    def _fail_closed(self) -> Settings:
        if self.app_env in ("production", "staging"):
            if self.demo_synthetic_policy_enabled:
                raise ValueError(
                    "DEMO_SYNTHETIC_POLICY_ENABLED is permitted only in local development/test."
                )
            if self.demo_mode:
                raise ValueError(
                    "DEMO_MODE must be false when APP_ENV is "
                    f"{self.app_env!r}: demo routes and the demo identity "
                    "switcher must never be reachable in a deployed environment."
                )
            if not self.database_url or self.database_url == _LOCAL_DATABASE_URL:
                raise ValueError(
                    f"DATABASE_URL must be set explicitly when APP_ENV is {self.app_env!r}"
                )
            if self.receipt_storage_backend == "local":
                raise ValueError(
                    "RECEIPT_STORAGE_BACKEND=local is not permitted outside local "
                    "development: receipt images must live in private object storage."
                )
            if self.auth_provider == "demo":
                raise ValueError(
                    f"AUTH_PROVIDER=demo is not permitted when APP_ENV is {self.app_env!r}"
                )

        if self.demo_synthetic_policy_enabled and (
            self.app_env not in ("development", "test") or not self.demo_mode
        ):
            raise ValueError(
                "DEMO_SYNTHETIC_POLICY_ENABLED requires DEMO_MODE=true in development or test."
            )

        if self.app_env == "production" and self.auth_provider == "supabase":
            missing = [
                name
                for name, value in (
                    ("SUPABASE_URL", self.supabase_url),
                    ("SUPABASE_JWT_ISSUER", self.supabase_jwt_issuer),
                    ("SUPABASE_JWKS_URL", self.supabase_jwks_url),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "Supabase auth is selected but required configuration is missing: "
                    + ", ".join(missing)
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so that configuration is parsed and validated once. Tests that need
    different settings must clear the cache via ``get_settings.cache_clear()``.
    """
    return Settings()


settings = get_settings()
