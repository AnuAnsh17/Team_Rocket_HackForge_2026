"""policy assignment scope selector kind

Revision ID: 0002_scope_selector
Revises: 0001_initial
Created: 2026-10-17

WHY THIS MIGRATION EXISTS
------------------------
A policy assignment's scope was identified by a single ``scope_id UUID`` column, but
three of the ten supported scope dimensions are not identified by a UUID:

* ``jurisdiction``      -- a code recorded on the organization, e.g. "IN-MH"
* ``legal_entity``      -- a name recorded on the organization; there is no
                           legal_entities table, so there is no id to point at
* ``expense_category``  -- free text on the claim, e.g. "meal"

The resolver compared ``str(scope_id)`` against those values, so an expense-category
assignment could NEVER match, and legal entity and jurisdiction were never matched at
all (they returned False unconditionally). An assignment that can never apply is worse
than a missing one: it looks configured.

This migration adds ``scope_key`` for text-valued dimensions, makes ``scope_id``
nullable, and adds a CHECK constraint that forces exactly the selector the dimension
needs. Which dimensions are which is defined once, in
``app/core/enums.py::UUID_VALUED_SCOPE_TYPES`` / ``TEXT_VALUED_SCOPE_TYPES``.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not add precedence, tie-breaking or any reimbursement rule. Resolution still
reports a conflict as unresolved rather than choosing.

It also does not touch the hand-written integrity indexes from 0001. Alembic's
autogenerate proposed dropping all fifteen of them (including
``uq_expense_field_evidence_current``, ``uq_duplicate_candidates_pair`` and
``uq_findings_identity``) because they are not visible in the model metadata. They were
reviewed and removed from this migration by hand.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_scope_selector"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PostgreSQL truncated the generated name to 63 characters when 0001 created it, so the
# shortened form is the real identifier.
_OLD_UNIQUE_CONSTRAINT = "uq_policy_assignments_organization_id_policy_version_id_0b9d"

# The selector CHECK. Built from the same classification the resolver uses, so a
# dimension cannot be added to the enum without also being given a storage rule.
_UPGRADE_CHECK = (
    "("
    "  scope_type IN ("
    "    'cost_center', 'department', 'employee', 'job_grade', 'office_location',"
    "    'organization', 'trip'"
    "  )"
    "  AND scope_id IS NOT NULL AND scope_key IS NULL"
    ") OR ("
    "  scope_type IN ('expense_category', 'jurisdiction', 'legal_entity')"
    "  AND scope_key IS NOT NULL AND scope_id IS NULL"
    ")"
)

# Uniqueness over the *effective* selector. A plain unique constraint cannot express
# this: PostgreSQL treats NULLs as distinct, and one of the two selector columns is
# always NULL, so ('org', v, 'jurisdiction', NULL, 'IN-MH') could be inserted twice.
# COALESCE removes that hole, and lower() matches the case-folding the resolver applies,
# so the database cannot hold two assignments the resolver would consider identical.
_UNIQUE_INDEX = (
    "CREATE UNIQUE INDEX uq_policy_assignments_scope_selector "
    "ON policy_assignments ("
    "    organization_id,"
    "    policy_version_id,"
    "    scope_type,"
    "    COALESCE(scope_id::text, ''),"
    "    lower(COALESCE(scope_key, ''))"
    ")"
)


def upgrade() -> None:
    op.add_column(
        "policy_assignments",
        sa.Column("scope_key", sa.String(length=200), nullable=True),
    )
    op.alter_column(
        "policy_assignments",
        "scope_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    # Replaced by the scope-selector unique index below.
    op.drop_constraint(_OLD_UNIQUE_CONSTRAINT, "policy_assignments", type_="unique")

    op.create_check_constraint(
        "scope_selector_consistent",
        "policy_assignments",
        _UPGRADE_CHECK,
    )

    op.execute(_UNIQUE_INDEX)

    # The resolver filters by scope_type and then matches on whichever selector applies.
    op.drop_index("ix_policy_assignments_scope", table_name="policy_assignments")
    op.create_index(
        "ix_policy_assignments_scope",
        "policy_assignments",
        ["scope_type", "scope_id", "scope_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_policy_assignments_scope", table_name="policy_assignments")
    op.create_index(
        "ix_policy_assignments_scope",
        "policy_assignments",
        ["scope_type", "scope_id"],
        unique=False,
    )

    op.execute("DROP INDEX IF EXISTS uq_policy_assignments_scope_selector")
    # Explicit DDL rather than op.drop_constraint: the MetaData naming convention is
    # re-applied to the name passed there, which would produce
    # "ck_policy_assignments_ck_policy_assignments_scope_selec_9692" and fail.
    op.execute(
        "ALTER TABLE policy_assignments "
        "DROP CONSTRAINT ck_policy_assignments_scope_selector_consistent"
    )

    # Restoring NOT NULL would fail on any text-dimension row, because those have a
    # NULL scope_id by design. A downgrade that silently deleted such rows would be
    # worse than one that refuses, so it refuses and says why.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM policy_assignments WHERE scope_id IS NULL) THEN
                RAISE EXCEPTION
                    'cannot downgrade: policy_assignments rows exist for text-valued scope '
                    'dimensions (legal entity, jurisdiction, expense category), which have no '
                    'scope_id. Remove or re-scope them first; this migration will not delete '
                    'them for you.';
            END IF;
        END
        $$
        """
    )
    op.alter_column(
        "policy_assignments",
        "scope_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_column("policy_assignments", "scope_key")

    op.create_unique_constraint(
        _OLD_UNIQUE_CONSTRAINT,
        "policy_assignments",
        ["organization_id", "policy_version_id", "scope_type", "scope_id"],
    )
