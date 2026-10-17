"""Shared test configuration and fixtures.

Two things here are worth understanding before adding tests.

**Environment first.** Application settings are parsed once and cached, so the
environment must be set before any application module is imported. This module
therefore configures the test environment at import time and only then imports the
app. It also derives a *separate* database name instead of reusing the development
database, so a test run cannot damage local data.

**Real schema, real database.** The integration and contract tests run against a
real PostgreSQL instance whose schema was produced by ``alembic upgrade head``.
That is deliberate: CHECK constraints, partial unique indexes, the append-only
trigger and NUMERIC money semantics are the things most likely to be wrong, and a
SQLite substitute would silently not test any of them.

**Rollback per test.** Each test runs inside a transaction that is rolled back, so
tests do not leak state into one another and the suite is order-independent.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

# --------------------------------------------------------------------------
# Environment. Must run before the first application import.
# --------------------------------------------------------------------------
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("AUTH_PROVIDER", "demo")
os.environ.setdefault("EXTRACTION_PROVIDER", "unavailable")
os.environ.setdefault("RECEIPT_STORAGE_BACKEND", "local")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_JSON", "false")

import app.core.config as app_config
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config as AlembicConfig
from app.core.config import Settings, get_settings
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _derive_test_database_url() -> str:
    """Point at a sibling database of the configured one.

    Honours TEST_DATABASE_URL when set; otherwise rewrites the last path segment of
    DATABASE_URL (from .env or the environment) to append ``_test``. The host and
    port therefore follow whatever the developer actually configured, including a
    non-default port used to avoid clashing with a locally installed PostgreSQL.
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = Settings().database_url
    head, _, database = base.rpartition("/")
    if not head:
        raise RuntimeError(f"Cannot derive a test database name from {base!r}")
    return f"{head}/{database}_test"


TEST_DATABASE_URL = _derive_test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
get_settings.cache_clear()
# The module-level settings singleton is created when app.core.config is first
# imported. Point it at the dedicated test database before Alembic or app modules
# import that singleton; otherwise tests can target the development database.
app_config.settings = get_settings()


def _ensure_test_database_exists() -> None:
    """Create the test database if it is missing.

    Connects to the ``postgres`` maintenance database because CREATE DATABASE cannot
    run inside a transaction against the target database.
    """
    head, _, database = TEST_DATABASE_URL.rpartition("/")
    admin_url = f"{head}/postgres"
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                sa.text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
            ).scalar()
            if not exists:
                connection.execute(sa.text(f'CREATE DATABASE "{database}"'))
    finally:
        engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _prepared_database(request: pytest.FixtureRequest) -> Iterator[None]:
    """Build the test schema with Alembic, once per session.

    Using the real migration rather than ``metadata.create_all`` means the
    migration itself is exercised by every test run. A migration that cannot be
    applied is a failure the suite reports immediately.
    """
    needs_database = any(
        {"client", "db", "engine"}.intersection(item.fixturenames) for item in request.session.items
    )
    if not needs_database:
        yield
        return

    _ensure_test_database_exists()
    config = AlembicConfig(os.path.join(_BACKEND_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(_BACKEND_ROOT, "migrations"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


@pytest.fixture(scope="session")
def engine(_prepared_database: None) -> Iterator[sa.Engine]:
    from app.db.session import dispose_engine, get_engine

    dispose_engine()
    engine = get_engine()
    yield engine
    dispose_engine()


@pytest.fixture
def db(engine: sa.Engine) -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session, tmp_path) -> Iterator[TestClient]:
    """A TestClient that shares the test's transaction.

    ``get_session`` is overridden so HTTP requests and direct fixture work see the
    same uncommitted data, and so the rollback above covers anything a request
    wrote.
    """
    from app.api.deps import get_receipt_storage, get_session
    from app.main import create_app
    from app.storage.local import LocalPrivateReceiptStorage

    app = create_app()

    def _override_get_session(request: Request) -> Iterator[Session]:
        try:
            yield db
            for callback in getattr(request.state, "commit_callbacks", []):
                callback()
        except Exception:
            for callback in getattr(request.state, "rollback_callbacks", []):
                callback()
            raise

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_receipt_storage] = lambda: LocalPrivateReceiptStorage(
        root=tmp_path / "private-receipts"
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db: Session) -> dict[str, object]:
    """Load the synthetic demo dataset and return the seeded identity ids."""
    from app.services import demo_service

    result = demo_service.seed_demo_dataset(db)
    return {
        "response": result,
        "subjects": {
            person.key: demo_service.demo_identity_subject(person.key)
            for person in demo_service.DEMO_PEOPLE
        },
    }


@pytest.fixture
def employee_headers(seeded: dict[str, object]) -> dict[str, str]:
    subjects = seeded["subjects"]
    assert isinstance(subjects, dict)
    return {"X-Demo-Actor-Id": subjects["employee.asha"]}


@pytest.fixture
def finance_headers(seeded: dict[str, object]) -> dict[str, str]:
    subjects = seeded["subjects"]
    assert isinstance(subjects, dict)
    return {"X-Demo-Actor-Id": subjects["finance.admin"]}


@pytest.fixture
def unknown_uuid() -> uuid.UUID:
    return uuid.uuid4()
