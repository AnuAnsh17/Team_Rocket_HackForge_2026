"""Database engine and session management.

Synchronous SQLAlchemy 2.x over psycopg3. See docs/architecture-decisions.md
("Synchronous persistence") for the rationale and for the containment boundary
that keeps a future async conversion cheap.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def create_db_engine(config: Settings | None = None) -> Engine:
    """Create a configured engine. Connection errors surface on first use, not here."""
    config = config or settings
    url = config.database_url

    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")

    kwargs: dict[str, object] = {
        "echo": config.database_echo,
        "pool_pre_ping": config.database_pool_pre_ping,
        "future": True,
    }
    # SQLite is used only by a small number of unit tests that do not need
    # PostgreSQL semantics; it does not accept pool sizing arguments.
    if url.startswith("sqlite"):
        kwargs.pop("pool_pre_ping", None)
    else:
        kwargs["pool_size"] = config.database_pool_size
        kwargs["max_overflow"] = config.database_max_overflow

    return create_engine(url, **kwargs)


def get_engine() -> Engine:
    """Process-wide engine singleton."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _session_factory


def dispose_engine() -> None:
    """Dispose the engine and forget the singletons. Used by test teardown."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for scripts and background work.

    Commits on clean exit, rolls back on any exception. HTTP request handling
    uses the FastAPI dependency in app/api/deps.py rather than this helper, so
    that the transaction boundary stays visible at the route layer.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connectivity() -> tuple[bool, str | None, float | None]:
    """Probe the database for the health endpoint.

    Returns ``(ok, error_code, latency_ms)``. The error is reduced to a stable
    code so a health response can never leak a DSN, driver message or host name.
    """
    import time

    started = time.perf_counter()
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False, "DATABASE_UNAVAILABLE", None
    return True, None, round((time.perf_counter() - started) * 1000, 2)
