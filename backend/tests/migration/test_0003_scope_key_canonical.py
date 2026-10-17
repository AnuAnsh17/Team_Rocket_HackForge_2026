"""Executes migration 0003 against disposable databases holding legacy rows.

WHY THESE TESTS EXIST
---------------------
The preflight in 0003 must refuse unsafe legacy data *before* it modifies anything. Two
things are needed to show that honestly, and static inspection of the source is neither:

1. A database in the **0002 state**, where the previous behaviour is still in force. In
   that state "in-mh" and " in-mh " are both storable (the 0002 index keys on
   ``lower(scope_key)``), and so are "Stra\u00dfe" and "STRASSE" -- because PostgreSQL's
   ``lower()`` is not Python's ``casefold()``. These rows cannot be created at HEAD: the
   CHECK constraint added by 0003 would reject the first and the unique index the second.
   So a test that only runs against the migrated schema cannot exercise the cases that
   matter.
2. A real execution, so the refusal is proven to happen before any DDL or DML, and the
   database is proven unchanged -- data, schema and the recorded revision.

Each test therefore creates its own disposable database, applies 0001 and 0002, seeds
legacy rows, then runs 0003 and inspects the outcome.

Alembic runs in a subprocess with ``DATABASE_URL`` in the environment, rather than through
in-process calls, because ``migrations/env.py`` takes the URL from the application
settings singleton. A subprocess is also closer to how a deploy or CI applies a migration.

An earlier revision of the migration would have passed a weaker version of these tests:
it grouped raw keys, so ``"in-mh"``/``" in-mh "`` were not detected as a collision, and it
backfilled with ``lower()``, so ``"Stra\u00dfe"``/``"STRASSE"`` would not have converged.
The Unicode case-fold test below is the one that catches that.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import sqlalchemy as sa

pytestmark = pytest.mark.migration

BACKEND_ROOT = Path(__file__).resolve().parents[2]

REV_0002 = "0002_scope_selector"
REV_0003 = "0003_scope_key_canonical"

_TEXT_SCOPE_TYPES = ("expense_category", "jurisdiction", "legal_entity")


# ---------------------------------------------------------------------------
# Disposable database
# ---------------------------------------------------------------------------


def _maintenance_base_url() -> str:
    """The connection prefix to borrow for the disposable databases."""
    url = os.environ["DATABASE_URL"]
    head, _, _database = url.rpartition("/")
    if not head:
        raise RuntimeError(f"Cannot derive a maintenance URL from {url!r}")
    return head


@contextmanager
def _disposable_database() -> Iterator[tuple[sa.Engine, str]]:
    """Create a throwaway database, hand back an engine and its URL, then drop it.

    The URL is built here and passed out rather than re-rendered from the engine, so no
    credential has to be un-hidden to hand it to the Alembic subprocess.
    """
    name = f"proofline_mig_{uuid.uuid4().hex[:12]}"
    url = f"{_maintenance_base_url()}/{name}"
    admin = sa.create_engine(f"{_maintenance_base_url()}/postgres", isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{name}"'))
        engine = sa.create_engine(url)
        try:
            yield engine, url
        finally:
            engine.dispose()
    finally:
        with admin.connect() as connection:
            connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run an Alembic command in a fresh process against ``url``."""
    environment = {
        **os.environ,
        "DATABASE_URL": url,
        "APP_ENV": "test",
        "DEMO_MODE": "false",
        "RECEIPT_STORAGE_BACKEND": "local",
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@contextmanager
def _database_at_0002() -> Iterator[tuple[sa.Engine, str]]:
    """A disposable database migrated to the pre-0003 revision."""
    with _disposable_database() as (engine, url):
        result = _alembic(url, "upgrade", REV_0002)
        assert result.returncode == 0, (
            f"could not migrate a disposable database to {REV_0002}:\n"
            f"{result.stdout}\n{result.stderr}"
        )
        yield engine, url


# ---------------------------------------------------------------------------
# Seeding legacy rows at the 0002 revision
# ---------------------------------------------------------------------------


def _seed(
    engine: sa.Engine,
    rows: list[tuple[str, str]],
    *,
    suffix: str = "a",
) -> dict[str, uuid.UUID]:
    """Insert one organization, version and a set of text-dimension assignments.

    Returns a mapping of ``scope_key`` -> assignment id, so a refusal message can be
    checked against the rows that were actually seeded.
    """
    organization_id = uuid.uuid4()
    version_id = uuid.uuid4()
    document_id = uuid.uuid4()
    user_id = uuid.uuid4()

    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO organizations (id, name, slug, is_demo, is_active, created_at,
                                           updated_at)
                VALUES (:id, :name, :slug, true, true, now(), now())
                """
            ),
            {
                "id": organization_id,
                "name": f"Legacy Org {suffix}",
                "slug": f"legacy-{suffix}-{organization_id.hex[:8]}",
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO users (id, display_name, is_active, created_at, updated_at)
                VALUES (:id, :name, true, now(), now())
                """
            ),
            {"id": user_id, "name": f"Legacy Approver {suffix}"},
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO policy_documents (id, title, authoritative, created_at, updated_at)
                VALUES (:id, :title, false, now(), now())
                """
            ),
            {"id": document_id, "title": f"Legacy Policy {suffix}"},
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO policy_versions (id, policy_document_id, version_label,
                    review_state, approved_by_user_id, approved_at, created_at, updated_at)
                VALUES (:id, :document_id, :label, 'approved', :approver, now(), now(), now())
                """
            ),
            {
                "id": version_id,
                "document_id": document_id,
                "label": f"legacy-{suffix}",
                "approver": user_id,
            },
        )

        assignment_ids: dict[str, uuid.UUID] = {}
        for scope_type, scope_key in rows:
            assignment_id = uuid.uuid4()
            connection.execute(
                sa.text(
                    """
                    INSERT INTO policy_assignments (id, organization_id, policy_version_id,
                        scope_type, scope_key, priority, approval_state, created_at, updated_at)
                    VALUES (:id, :organization_id, :version_id, :scope_type, :scope_key,
                            0, 'approved', now(), now())
                    """
                ),
                {
                    "id": assignment_id,
                    "organization_id": organization_id,
                    "version_id": version_id,
                    "scope_type": scope_type,
                    "scope_key": scope_key,
                },
            )
            assignment_ids[scope_key] = assignment_id

    return assignment_ids


# ---------------------------------------------------------------------------
# Inspection helpers
# ---------------------------------------------------------------------------


def _stored_keys(engine: sa.Engine) -> dict[uuid.UUID, str]:
    with engine.connect() as connection:
        return {
            row.id: row.scope_key
            for row in connection.execute(
                sa.text("SELECT id, scope_key FROM policy_assignments ORDER BY scope_key")
            )
        }


def _revision(engine: sa.Engine) -> str | None:
    with engine.connect() as connection:
        return connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()


def _index_def(engine: sa.Engine) -> str:
    with engine.connect() as connection:
        return (
            connection.execute(
                sa.text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE indexname = 'uq_policy_assignments_scope_selector'"
                )
            ).scalar()
            or ""
        )


def _has_canonical_check(engine: sa.Engine) -> bool:
    with engine.connect() as connection:
        return bool(
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conname = 'ck_policy_assignments_scope_key_canonical'"
                )
            ).scalar()
        )


def _integrity_index_count(engine: sa.Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(
            sa.text(
                """
                SELECT count(*) FROM pg_indexes
                WHERE schemaname = 'public'
                  AND (indexname LIKE 'uq_expense_field%'
                       OR indexname LIKE 'uq_duplicate%'
                       OR indexname = 'uq_findings_identity'
                       OR indexname LIKE 'ix_audit%')
                """
            )
        ).scalar()


def _append_only_trigger_count(engine: sa.Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(
            sa.text("SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_audit_events_append_only'")
        ).scalar()


# ---------------------------------------------------------------------------
# Refusals: unsafe legacy data is rejected BEFORE anything changes
# ---------------------------------------------------------------------------


class TestRefusals:
    def test_a_whitespace_normalization_collision_is_refused(self) -> None:
        """``"in-mh"`` and ``" in-mh "`` are one key to the resolver, two to the 0002 index.

        Grouping raw keys -- as an earlier revision did -- would not detect this, so the
        migration would have proceeded and then failed building the unique index, or (with
        the old lower()-based backfill) silently kept both.
        """
        with _database_at_0002() as (engine, url):
            seeded = _seed(engine, [("jurisdiction", "in-mh"), ("jurisdiction", " in-mh ")])
            before = _stored_keys(engine)

            result = _alembic(url, "upgrade", REV_0003)

            assert result.returncode != 0, "the migration must refuse this data"
            message = result.stdout + result.stderr
            assert "scope keys" in message
            assert "does not choose a winner" in message
            # Reported with the affected ids and the original keys.
            assert str(seeded["in-mh"]) in message
            assert str(seeded[" in-mh "]) in message
            assert "'in-mh'" in message and "' in-mh '" in message

            # Nothing changed: data, schema and recorded revision.
            assert _stored_keys(engine) == before
            assert _has_canonical_check(engine) is False
            assert "lower" in _index_def(engine), "the 0002 index must still be in place"
            assert _revision(engine) == REV_0002

    def test_a_unicode_case_fold_collision_is_refused(self) -> None:
        """``"Stra\u00dfe"`` and ``"STRASSE"`` are one key to ``casefold()``.

        PostgreSQL's ``lower()`` maps them to different strings, so a lower()-based preflight
        would miss this entirely and a lower()-based backfill would leave both rows in place
        -- exactly the duplicate the migration exists to prevent.
        """
        with _database_at_0002() as (engine, url):
            seeded = _seed(engine, [("legal_entity", "Stra\u00dfe"), ("legal_entity", "STRASSE")])
            before = _stored_keys(engine)

            result = _alembic(url, "upgrade", REV_0003)

            assert result.returncode != 0, (
                "casefold treats these as one key, so the migration must refuse"
            )
            message = result.stdout + result.stderr
            assert "does not choose a winner" in message
            assert str(seeded["Stra\u00dfe"]) in message
            assert str(seeded["STRASSE"]) in message
            # The collision is reported under the canonical value both would become.
            assert "'strasse'" in message

            assert _stored_keys(engine) == before
            assert _has_canonical_check(engine) is False
            assert _revision(engine) == REV_0002

    @pytest.mark.parametrize(
        "blank",
        ["\t", "\xa0", "   ", "\u3000", " \t\xa0 "],
        ids=["tab", "nbsp", "spaces", "ideographic", "mixed"],
    )
    def test_a_whitespace_only_key_is_refused(self, blank: str) -> None:
        """A default ``btrim()`` would treat ``"\t"`` and ``"\xa0"`` as real keys.

        They normalize to nothing under the contract, so such an assignment can never match
        a claim and must be refused rather than backfilled into a blank key.
        """
        with _database_at_0002() as (engine, url):
            seeded = _seed(engine, [("expense_category", blank)])
            before = _stored_keys(engine)

            result = _alembic(url, "upgrade", REV_0003)

            assert result.returncode != 0, f"a {blank!r} key must be refused"
            message = result.stdout + result.stderr
            assert "whitespace-only" in message
            assert str(seeded[blank]) in message

            assert _stored_keys(engine) == before
            assert _has_canonical_check(engine) is False
            assert _revision(engine) == REV_0002

    def test_a_failed_preflight_leaves_the_database_exactly_as_it_was(self) -> None:
        """The schema, the data and the revision are all unchanged by a refusal."""
        with _database_at_0002() as (engine, url):
            _seed(engine, [("jurisdiction", "in-mh"), ("jurisdiction", " in-mh ")])
            before_rows = _stored_keys(engine)
            before_index = _index_def(engine)
            with engine.connect() as connection:
                before_columns = connection.execute(
                    sa.text(
                        "SELECT count(*) FROM information_schema.columns "
                        "WHERE table_name = 'policy_assignments'"
                    )
                ).scalar()
                before_tables = connection.execute(
                    sa.text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                    )
                ).scalar()

            result = _alembic(url, "upgrade", REV_0003)
            assert result.returncode != 0

            assert _stored_keys(engine) == before_rows
            assert _index_def(engine) == before_index
            assert _has_canonical_check(engine) is False
            assert _revision(engine) == REV_0002
            with engine.connect() as connection:
                assert (
                    connection.execute(
                        sa.text(
                            "SELECT count(*) FROM information_schema.columns "
                            "WHERE table_name = 'policy_assignments'"
                        )
                    ).scalar()
                    == before_columns
                )
                assert (
                    connection.execute(
                        sa.text(
                            "SELECT count(*) FROM information_schema.tables "
                            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                        )
                    ).scalar()
                    == before_tables
                )
                # No half-applied DDL: the canonical index and the old index cannot both
                # exist, and the old one cannot be missing.
                assert (
                    connection.execute(
                        sa.text(
                            "SELECT count(*) FROM pg_indexes "
                            "WHERE indexname = 'uq_policy_assignments_scope_selector'"
                        )
                    ).scalar()
                    == 1
                )


# ---------------------------------------------------------------------------
# Success: safe legacy data is canonicalised
# ---------------------------------------------------------------------------


class TestSuccessfulUpgrade:
    def test_distinct_canonical_keys_are_canonicalised_and_allowed(self) -> None:
        """Mixed case, surrounding and internal whitespace all converge; distinct stays distinct."""
        with _database_at_0002() as (engine, url):
            _seed(
                engine,
                [
                    ("jurisdiction", " IN-MH "),
                    ("jurisdiction", "in-ka"),
                    ("expense_category", "Meal"),
                    ("legal_entity", "Example  Consulting  Pvt Ltd"),
                ],
            )

            result = _alembic(url, "upgrade", REV_0003)
            assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

            stored = sorted(_stored_keys(engine).values())
            assert stored == [
                "example consulting pvt ltd",
                "in-ka",
                "in-mh",
                "meal",
            ], stored

            # The new schema is in place and the database-side check is satisfied.
            assert _has_canonical_check(engine) is True
            assert "lower" not in _index_def(engine), (
                "the canonical index must not apply a second normalization"
            )
            assert _revision(engine) == REV_0003

    def test_keys_already_canonical_are_left_untouched(self) -> None:
        with _database_at_0002() as (engine, url):
            seeded = _seed(engine, [("jurisdiction", "in-mh"), ("expense_category", "meal")])

            result = _alembic(url, "upgrade", REV_0003)
            assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

            stored = _stored_keys(engine)
            for key, assignment_id in seeded.items():
                # Same id, same value: the migration rewrote nothing it did not need to.
                assert stored[assignment_id] == key

    def test_integrity_indexes_and_the_append_only_trigger_survive_the_upgrade(self) -> None:
        with _database_at_0002() as (engine, url):
            _seed(engine, [("jurisdiction", " IN-MH ")])
            assert _integrity_index_count(engine) == 8
            assert _append_only_trigger_count(engine) == 1

            result = _alembic(url, "upgrade", REV_0003)
            assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

            assert _integrity_index_count(engine) == 8
            assert _append_only_trigger_count(engine) == 1

    def test_downgrade_then_upgrade_round_trips(self) -> None:
        """The revision is reversible, and re-applying it is idempotent on canonical data."""
        with _database_at_0002() as (engine, url):
            _seed(engine, [("jurisdiction", " IN-MH ")])

            assert _alembic(url, "upgrade", REV_0003).returncode == 0
            assert sorted(_stored_keys(engine).values()) == ["in-mh"]

            down = _alembic(url, "downgrade", REV_0002)
            assert down.returncode == 0, f"{down.stdout}\n{down.stderr}"
            assert _has_canonical_check(engine) is False
            assert "lower" in _index_def(engine), "the 0002 index must be restored"
            assert _integrity_index_count(engine) == 8
            assert _append_only_trigger_count(engine) == 1

            up = _alembic(url, "upgrade", REV_0003)
            assert up.returncode == 0, f"{up.stdout}\n{up.stderr}"
            assert sorted(_stored_keys(engine).values()) == ["in-mh"]
            assert _has_canonical_check(engine) is True
            assert "lower" not in _index_def(engine)

    def test_the_new_unique_index_rejects_a_whitespace_variant_after_upgrade(self) -> None:
        """The end the whole migration exists for, exercised against the migrated schema."""
        with _database_at_0002() as (engine, url):
            seeded = _seed(engine, [("jurisdiction", " in-mh ")])
            organization_and_version = None
            with engine.connect() as connection:
                organization_and_version = connection.execute(
                    sa.text(
                        "SELECT organization_id, policy_version_id FROM policy_assignments "
                        "WHERE id = :id"
                    ),
                    {"id": next(iter(seeded.values()))},
                ).one()

            assert _alembic(url, "upgrade", REV_0003).returncode == 0

            with (
                engine.begin() as connection,
                pytest.raises(sa.exc.IntegrityError) as caught,
            ):
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO policy_assignments (id, organization_id,
                            policy_version_id, scope_type, scope_key, priority,
                            approval_state, created_at, updated_at)
                        VALUES (:id, :organization_id, :version_id, 'jurisdiction',
                                'in-mh ', 0, 'approved', now(), now())
                        """
                    ),
                    {
                        "id": uuid.uuid4(),
                        "organization_id": organization_and_version[0],
                        "version_id": organization_and_version[1],
                    },
                )
            assert "scope_key_canonical" in str(caught.value)
