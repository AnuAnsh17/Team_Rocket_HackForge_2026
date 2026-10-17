"""Persist validated structured extraction and bounded worker attempts.

Revision ID: 0004_receipt_extraction_results
Revises: 0003_scope_key_canonical
Created: 2026-10-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_receipt_extraction_results"
down_revision = "0003_scope_key_canonical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "extraction_runs",
        sa.Column("structured_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "extraction_runs",
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "extraction_runs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "attempt_count_non_negative", "extraction_runs", "attempt_count >= 0"
    )
    op.create_check_constraint(
        "structured_result_matches_status",
        "extraction_runs",
        "structured_result IS NULL OR status IN ('success', 'partial')",
    )
    op.create_check_constraint(
        "validation_requires_structured_result",
        "extraction_runs",
        "validation_result IS NULL OR structured_result IS NOT NULL",
    )
    op.alter_column("extraction_runs", "attempt_count", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_extraction_runs_validation_requires_structured_result"),
        "extraction_runs",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_extraction_runs_structured_result_matches_status"),
        "extraction_runs",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_extraction_runs_attempt_count_non_negative"),
        "extraction_runs",
        type_="check",
    )
    op.drop_column("extraction_runs", "attempt_count")
    op.drop_column("extraction_runs", "validation_result")
    op.drop_column("extraction_runs", "structured_result")
