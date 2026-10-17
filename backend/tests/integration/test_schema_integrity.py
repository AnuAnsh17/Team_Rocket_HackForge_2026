"""Schema-level guarantees that only a real database can demonstrate.

These assertions are the reason the suite runs against PostgreSQL rather than
SQLite: partial unique indexes, CHECK constraints and a trigger have no meaningful
equivalent elsewhere.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "allowance_profile_items",
    "allowance_profiles",
    "approval_tasks",
    "audit_events",
    "cost_centers",
    "departments",
    "duplicate_candidates",
    "expense_field_evidence",
    "expenses",
    "extraction_runs",
    "findings",
    "idempotency_keys",
    "job_grades",
    "line_items",
    "office_locations",
    "organization_memberships",
    "organizations",
    "policy_assignments",
    "policy_documents",
    "policy_exceptions",
    "policy_rules",
    "policy_versions",
    "receipts",
    "reporting_relationships",
    "review_decisions",
    "role_assignments",
    "trips",
    "users",
}


class TestSchemaShape:
    def test_every_expected_table_exists(self, db: Session) -> None:
        present = set(sa.inspect(db.get_bind()).get_table_names())
        assert present >= EXPECTED_TABLES

    def test_hand_written_integrity_indexes_exist(self, db: Session) -> None:
        rows = (
            db.execute(sa.text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"))
            .scalars()
            .all()
        )
        for name in (
            "uq_expense_field_evidence_current",
            "uq_duplicate_candidates_pair",
            "uq_findings_identity",
            "ix_audit_events_entity",
            "ix_receipts_organization_sha256",
        ):
            assert name in rows, f"missing hand-written index {name}"

    def test_append_only_trigger_is_installed(self, db: Session) -> None:
        count = db.execute(
            sa.text("SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_audit_events_append_only'")
        ).scalar()
        assert count == 1

    def test_money_columns_are_numeric_not_float(self, db: Session) -> None:
        rows = db.execute(
            sa.text(
                """
                SELECT table_name, column_name, data_type, numeric_precision
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name IN ('amount', 'limit_amount', 'amount_reporting')
                  AND table_name IN ('expenses', 'allowance_profile_items')
                """
            )
        ).all()
        assert rows, "expected money columns to be present"
        for table_name, column_name, data_type, precision in rows:
            assert data_type == "numeric", (
                f"{table_name}.{column_name} must be numeric, got {data_type}"
            )
            assert precision and precision >= 18


class TestAuditAppendOnly:
    """The database, not the application, refuses to rewrite history."""

    def _insert_event(
        self, connection: sa.Connection, organization_id: uuid.UUID | None = None
    ) -> uuid.UUID:
        event_id = uuid.uuid4()
        connection.execute(
            sa.text(
                """
                INSERT INTO audit_events
                    (id, organization_id, actor_type, action, entity_type, entity_id, created_at)
                VALUES
                    (:id, :organization_id, 'system', 'test.append_only', 'audit_event',
                     :entity_id, now())
                """
            ),
            {"id": event_id, "organization_id": organization_id, "entity_id": uuid.uuid4()},
        )
        return event_id

    def test_update_is_refused_by_the_database(self, engine: sa.Engine) -> None:
        connection = engine.connect()
        transaction = connection.begin()
        try:
            event_id = self._insert_event(connection)
            # A RestrictViolation raised by the trigger arrives as IntegrityError.
            with pytest.raises(sa.exc.IntegrityError) as excinfo:
                connection.execute(
                    sa.text("UPDATE audit_events SET action = 'tampered' WHERE id = :id"),
                    {"id": event_id},
                )
            assert "append-only" in str(excinfo.value)
            transaction.rollback()
        finally:
            connection.close()

    def test_deleting_a_parent_row_does_not_try_to_rewrite_audit_history(
        self, engine: sa.Engine
    ) -> None:
        """Regression: audit_events must carry no cascading foreign keys.

        With an ``ON DELETE SET NULL`` foreign key, deleting an organization made
        PostgreSQL issue ``UPDATE audit_events SET organization_id = NULL``, which
        the append-only trigger refused. Deleting a parent row must instead succeed
        and leave the audit record intact - an audit trail that disappears with its
        subject is not an audit trail.
        """
        connection = engine.connect()
        transaction = connection.begin()
        try:
            constraint_count = connection.execute(
                sa.text(
                    """
                    SELECT count(*) FROM pg_constraint
                    WHERE conrelid = 'audit_events'::regclass AND contype = 'f'
                    """
                )
            ).scalar()
            assert constraint_count == 0, (
                "audit_events must not have foreign keys: a cascading action would "
                "make the database try to UPDATE or DELETE an append-only table"
            )

            organization_id = uuid.uuid4()
            connection.execute(
                sa.text(
                    """
                    INSERT INTO organizations
                        (id, name, slug, is_demo, is_active, created_at, updated_at)
                    VALUES (:id, 'Cascade Check', :slug, true, true, now(), now())
                    """
                ),
                {"id": organization_id, "slug": f"cascade-check-{organization_id.hex[:8]}"},
            )
            event_id = self._insert_event(connection, organization_id=organization_id)

            connection.execute(
                sa.text("DELETE FROM organizations WHERE id = :id"), {"id": organization_id}
            )

            surviving = connection.execute(
                sa.text("SELECT organization_id FROM audit_events WHERE id = :id"),
                {"id": event_id},
            ).scalar()
            assert surviving == organization_id, (
                "the audit event must survive deletion of the organization it references"
            )
            transaction.rollback()
        finally:
            connection.close()

    def test_delete_is_refused_by_the_database(self, engine: sa.Engine) -> None:
        connection = engine.connect()
        transaction = connection.begin()
        try:
            event_id = self._insert_event(connection)
            with pytest.raises(sa.exc.IntegrityError) as excinfo:
                connection.execute(
                    sa.text("DELETE FROM audit_events WHERE id = :id"), {"id": event_id}
                )
            assert "append-only" in str(excinfo.value)
            transaction.rollback()
        finally:
            connection.close()


class TestConstraintEnforcement:
    def test_an_unsourced_allowance_limit_is_refused(self, db: Session) -> None:
        organization_id = uuid.uuid4()
        db.execute(
            sa.text(
                """
                INSERT INTO organizations (id, name, slug, is_demo, is_active, created_at, updated_at)
                VALUES (:id, 'Constraint Test', :slug, false, true, now(), now())
                """
            ),
            {"id": organization_id, "slug": f"constraint-test-{organization_id.hex[:8]}"},
        )
        profile_id = uuid.uuid4()
        db.execute(
            sa.text(
                """
                INSERT INTO allowance_profiles
                    (id, organization_id, code, name, review_state, created_at, updated_at)
                VALUES (:id, :org, 'P1', 'Profile', 'draft', now(), now())
                """
            ),
            {"id": profile_id, "org": organization_id},
        )
        db.flush()
        with pytest.raises(sa.exc.IntegrityError) as excinfo:
            db.execute(
                sa.text(
                    """
                    INSERT INTO allowance_profile_items
                        (id, allowance_profile_id, period_type, limit_amount, source_clause,
                         created_at)
                    VALUES (:id, :profile, 'month', 5000.00, NULL, now())
                    """
                ),
                {"id": uuid.uuid4(), "profile": profile_id},
            )
        assert "limit_requires_source" in str(excinfo.value)

    def test_an_active_rule_without_a_validator_is_refused(self, db: Session) -> None:
        organization_id = uuid.uuid4()
        db.execute(
            sa.text(
                """
                INSERT INTO organizations (id, name, slug, is_demo, is_active, created_at, updated_at)
                VALUES (:id, 'Rule Test', :slug, false, true, now(), now())
                """
            ),
            {"id": organization_id, "slug": f"rule-test-{organization_id.hex[:8]}"},
        )
        document_id, version_id = uuid.uuid4(), uuid.uuid4()
        db.execute(
            sa.text(
                """
                INSERT INTO policy_documents (id, organization_id, title, authoritative, created_at, updated_at)
                VALUES (:id, :org, 'Doc', false, now(), now())
                """
            ),
            {"id": document_id, "org": organization_id},
        )
        db.execute(
            sa.text(
                """
                INSERT INTO policy_versions
                    (id, policy_document_id, version_label, review_state, created_at, updated_at)
                VALUES (:id, :doc, 'v1', 'draft', now(), now())
                """
            ),
            {"id": version_id, "doc": document_id},
        )
        db.flush()
        with pytest.raises(sa.exc.IntegrityError) as excinfo:
            db.execute(
                sa.text(
                    """
                    INSERT INTO policy_rules
                        (id, policy_version_id, rule_id, title, review_state, is_active,
                         source_clause, validated_by_user_id, validated_at, created_at, updated_at)
                    VALUES (:id, :version, 'POLICY-X', 'Invented rule', 'approved', true,
                            NULL, NULL, NULL, now(), now())
                    """
                ),
                {"id": uuid.uuid4(), "version": version_id},
            )
        assert "source_requires_validation" in str(excinfo.value)

    def test_rejecting_a_claim_without_a_reason_is_refused(self, db: Session) -> None:
        """A rejection must carry a human explanation, enforced by the schema."""
        constraint = db.execute(
            sa.text(
                "SELECT conname FROM pg_constraint WHERE conname = 'ck_review_decisions_rejection_requires_reason'"
            )
        ).scalar()
        assert constraint == "ck_review_decisions_rejection_requires_reason"
