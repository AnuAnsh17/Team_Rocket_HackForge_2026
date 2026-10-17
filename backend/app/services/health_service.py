"""Health reporting.

The health payload is deliberately shallow. It reports component *status codes*,
never a DSN, host name, driver message or provider payload, because a health
endpoint is frequently unauthenticated and is a favourite reconnaissance target.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.db.session import check_database_connectivity
from app.schemas.health import HealthComponent, HealthResponse

API_VERSION = "v1"


def build_health_report(config: Settings | None = None) -> HealthResponse:
    """Assemble the health response, including a real database probe."""
    config = config or default_settings

    ok, error_code, latency_ms = check_database_connectivity()
    components: dict[str, HealthComponent] = {
        "database": HealthComponent(
            status="ok" if ok else "unavailable",
            detail=error_code,
            latency_ms=latency_ms,
        ),
    }

    # Reporting a stub as "ok" would be a lie, so unimplemented dependencies say so.
    components["receipt_storage"] = HealthComponent(
        status="ok" if config.receipt_storage_backend == "local" else "not_implemented",
        detail=(
            "local private filesystem (development only)"
            if config.receipt_storage_backend == "local"
            else f"{config.receipt_storage_backend} adapter is not implemented"
        ),
    )
    components["extraction_provider"] = HealthComponent(
        status="not_configured"
        if config.extraction_provider == "unavailable"
        else "not_implemented",
        detail=(
            "no extraction provider has been selected or verified"
            if config.extraction_provider == "unavailable"
            else f"{config.extraction_provider} adapter is not implemented"
        ),
    )
    components["authentication"] = HealthComponent(
        status="ok"
        if config.demo_routes_enabled and config.auth_provider == "demo"
        else "not_implemented",
        detail=(
            "demo identity provider active (non-production only)"
            if config.demo_routes_enabled and config.auth_provider == "demo"
            else "no production identity provider is implemented"
        ),
    )
    components["policy_engine"] = HealthComponent(
        status="not_configured",
        detail=(
            "the engine is implemented but holds zero active rules: no approved policy "
            "document has been supplied, so every evaluation returns UNKNOWN"
        ),
    )

    statuses = {component.status for component in components.values()}
    if "unavailable" in statuses:
        overall = "unavailable"
    elif statuses - {"ok"}:
        overall = "degraded"
    else:
        overall = "ok"

    return HealthResponse(
        status=overall,
        app_version=config.app_version,
        api_version=API_VERSION,
        environment=config.app_env,
        demo_mode=config.demo_routes_enabled,
        checked_at=datetime.now(UTC),
        components=components,
    )
