"""Policy-assignment scope resolution against real PostgreSQL.

Two things are verified here that a unit test cannot:

1. The database refuses a scope assignment whose selector does not match its
   dimension. ``ck_policy_assignments_scope_selector_consistent`` makes the defect this
   change fixes unstorable rather than merely unlikely: a category assignment cannot be
   saved with a UUID selector, and a UUID-valued dimension cannot be saved with a text
   key.
2. ``resolve_effective_policy`` resolves end to end against stored rows, including the
   three dimensions that previously could never match (expense category, jurisdiction,
   legal entity).

No precedence, threshold or reimbursement rule is asserted or introduced. Where two
approved versions could compete, the expectation is *unresolved* -- the resolver reports
the conflict rather than inventing a tie-break.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
import sqlalchemy as sa
from app.core.enums import PolicyAssignmentScopeType
from app.policy.base import EvaluationScope
from app.policy.resolution import resolve_effective_policy
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

ON_DATE = dt.date(2026, 3, 15)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _insert_organization(
    session: Session, *, jurisdiction: str | None, legal_entity: str | None
) -> uuid.UUID:
    organization_id = uuid.uuid4()
    session.execute(
        sa.text(
            """
            INSERT INTO organizations
                (id, name, slug, legal_entity_name, jurisdiction_code, is_demo, is_active,
                 created_at, updated_at)
            VALUES (:id, :name, :slug, :legal_entity, :jurisdiction, true, true, now(), now())
            """
        ),
        {
            "id": organization_id,
            "name": "Scope Test Org",
            "slug": f"scope-test-{organization_id.hex[:8]}",
            "legal_entity": legal_entity,
            "jurisdiction": jurisdiction,
        },
    )
    return organization_id


def _insert_approved_version(session: Session, *, label: str) -> uuid.UUID:
    """Insert an approved policy version, which requires an approver and timestamp."""
    user_id = uuid.uuid4()
    session.execute(
        sa.text(
            """
            INSERT INTO users (id, display_name, is_active, created_at, updated_at)
            VALUES (:id, 'Scope Test Approver', true, now(), now())
            """
        ),
        {"id": user_id},
    )
    document_id = uuid.uuid4()
    session.execute(
        sa.text(
            """
            INSERT INTO policy_documents (id, title, authoritative, created_at, updated_at)
            VALUES (:id, 'Scope Test Policy', false, now(), now())
            """
        ),
        {"id": document_id},
    )
    version_id = uuid.uuid4()
    session.execute(
        sa.text(
            """
            INSERT INTO policy_versions
                (id, policy_document_id, version_label, review_state, approved_by_user_id,
                 approved_at, created_at, updated_at)
            VALUES (:id, :document_id, :label, 'approved', :approver, now(), now(), now())
            """
        ),
        {
            "id": version_id,
            "document_id": document_id,
            "label": label,
            "approver": user_id,
        },
    )
    return version_id


def _insert_assignment(
    session: Session,
    *,
    organization_id: uuid.UUID,
    policy_version_id: uuid.UUID,
    scope_type: PolicyAssignmentScopeType,
    scope_id: uuid.UUID | None = None,
    scope_key: str | None = None,
    priority: int = 0,
    approval_state: str = "approved",
    effective_from: dt.date | None = None,
    effective_to: dt.date | None = None,
) -> uuid.UUID:
    assignment_id = uuid.uuid4()
    session.execute(
        sa.text(
            """
            INSERT INTO policy_assignments
                (id, organization_id, policy_version_id, scope_type, scope_id, scope_key,
                 priority, approval_state, effective_from, effective_to, created_at, updated_at)
            VALUES (:id, :organization_id, :policy_version_id, :scope_type, :scope_id, :scope_key,
                    :priority, :approval_state, :effective_from, :effective_to, now(), now())
            """
        ),
        {
            "id": assignment_id,
            "organization_id": organization_id,
            "policy_version_id": policy_version_id,
            "scope_type": scope_type.value,
            "scope_id": scope_id,
            "scope_key": scope_key,
            "priority": priority,
            "approval_state": approval_state,
            "effective_from": effective_from,
            "effective_to": effective_to,
        },
    )
    return assignment_id


def _scope(
    organization_id: uuid.UUID,
    *,
    category: str | None = None,
    jurisdiction: str | None = None,
    legal_entity: str | None = None,
    department_id: uuid.UUID | None = None,
) -> EvaluationScope:
    return EvaluationScope(
        organization_id=organization_id,
        membership_id=uuid.uuid4(),
        category=category,
        jurisdiction_code=jurisdiction,
        legal_entity_name=legal_entity,
        department_id=department_id,
    )


# ---------------------------------------------------------------------------
# The database refuses a selector that does not match its dimension
# ---------------------------------------------------------------------------


class TestSelectorConstraint:
    def test_a_text_dimension_cannot_be_stored_with_a_uuid_selector(self, db: Session) -> None:
        """The exact shape of the original defect."""
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="ck-text-with-uuid")
        with pytest.raises(sa.exc.IntegrityError) as caught:
            _insert_assignment(
                db,
                organization_id=organization_id,
                policy_version_id=version_id,
                scope_type=PolicyAssignmentScopeType.EXPENSE_CATEGORY,
                scope_id=uuid.uuid4(),
                scope_key=None,
            )
            db.flush()
        assert "scope_selector_consistent" in str(caught.value)

    def test_a_uuid_dimension_cannot_be_stored_with_a_text_selector(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="ck-uuid-with-text")
        with pytest.raises(sa.exc.IntegrityError) as caught:
            _insert_assignment(
                db,
                organization_id=organization_id,
                policy_version_id=version_id,
                scope_type=PolicyAssignmentScopeType.DEPARTMENT,
                scope_id=None,
                scope_key="some-department",
            )
            db.flush()
        assert "scope_selector_consistent" in str(caught.value)

    def test_a_selector_is_required(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="ck-no-selector")
        with pytest.raises(sa.exc.IntegrityError):
            _insert_assignment(
                db,
                organization_id=organization_id,
                policy_version_id=version_id,
                scope_type=PolicyAssignmentScopeType.JURISDICTION,
                scope_id=None,
                scope_key=None,
            )
            db.flush()

    def test_both_selectors_together_are_refused(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="ck-both-selectors")
        with pytest.raises(sa.exc.IntegrityError):
            _insert_assignment(
                db,
                organization_id=organization_id,
                policy_version_id=version_id,
                scope_type=PolicyAssignmentScopeType.JURISDICTION,
                scope_id=uuid.uuid4(),
                scope_key="IN-MH",
            )
            db.flush()

    def test_a_duplicate_text_dimension_assignment_is_refused(self, db: Session) -> None:
        """Uniqueness over the effective selector.

        A plain unique constraint could not express this: PostgreSQL treats NULLs as
        distinct, and a text-dimension row has a NULL scope_id, so the same assignment
        could otherwise be inserted twice.
        """
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="uq-text-dimension")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.JURISDICTION,
            scope_key="IN-MH",
        )
        db.flush()
        with pytest.raises(sa.exc.IntegrityError):
            _insert_assignment(
                db,
                organization_id=organization_id,
                policy_version_id=version_id,
                scope_type=PolicyAssignmentScopeType.JURISDICTION,
                scope_key="IN-MH",
            )
            db.flush()

    def test_a_case_differing_duplicate_is_also_refused(self, db: Session) -> None:
        # The unique index lower()s the key, matching the case folding the resolver
        # applies, so the database cannot hold two assignments the resolver would
        # consider identical.
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="uq-text-case")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.JURISDICTION,
            scope_key="IN-MH",
        )
        db.flush()
        with pytest.raises(sa.exc.IntegrityError):
            _insert_assignment(
                db,
                organization_id=organization_id,
                policy_version_id=version_id,
                scope_type=PolicyAssignmentScopeType.JURISDICTION,
                scope_key="in-mh",
            )
            db.flush()

    def test_distinct_text_keys_are_allowed(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="uq-text-distinct")
        for key in ("IN-MH", "IN-KA"):
            _insert_assignment(
                db,
                organization_id=organization_id,
                policy_version_id=version_id,
                scope_type=PolicyAssignmentScopeType.JURISDICTION,
                scope_key=key,
            )
        db.flush()  # no error expected


# ---------------------------------------------------------------------------
# End-to-end resolution through the real resolver
# ---------------------------------------------------------------------------


class TestResolutionPerDimension:
    def test_an_expense_category_assignment_resolves(self, db: Session) -> None:
        """The regression: this could never resolve before."""
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="resolve-category")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.EXPENSE_CATEGORY,
            scope_key="meal",
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, category="meal"),
            on_date=ON_DATE,
        )
        assert result.resolved is True
        assert result.policy_version_id == version_id
        assert [a.scope_type for a in result.applied_assignments] == ["expense_category"]
        assert result.applied_assignments[0].scope_key == "meal"
        assert result.applied_assignments[0].scope_id is None

    def test_a_jurisdiction_assignment_resolves(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction="IN-MH", legal_entity=None)
        version_id = _insert_approved_version(db, label="resolve-jurisdiction")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.JURISDICTION,
            scope_key="IN-MH",
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, jurisdiction="IN-MH"),
            on_date=ON_DATE,
        )
        assert result.resolved is True
        assert result.policy_version_id == version_id

    def test_a_legal_entity_assignment_resolves(self, db: Session) -> None:
        organization_id = _insert_organization(
            db, jurisdiction=None, legal_entity="Example Consulting Pvt Ltd"
        )
        version_id = _insert_approved_version(db, label="resolve-legal-entity")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.LEGAL_ENTITY,
            scope_key="Example Consulting Pvt Ltd",
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, legal_entity="Example Consulting Pvt Ltd"),
            on_date=ON_DATE,
        )
        assert result.resolved is True
        assert result.policy_version_id == version_id

    def test_an_organization_assignment_resolves(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="resolve-organization")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.ORGANIZATION,
            scope_id=organization_id,
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id),
            on_date=ON_DATE,
        )
        assert result.resolved is True

    def test_a_department_assignment_resolves_against_its_uuid(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="resolve-department")
        department_id = uuid.uuid4()
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.DEPARTMENT,
            scope_id=department_id,
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, department_id=department_id),
            on_date=ON_DATE,
        )
        assert result.resolved is True

        # A different department must not pick it up.
        other = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, department_id=uuid.uuid4()),
            on_date=ON_DATE,
        )
        assert other.resolved is False


class TestResolutionStaysHonest:
    def test_a_non_matching_text_key_leaves_the_policy_unresolved(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="resolve-no-match")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.EXPENSE_CATEGORY,
            scope_key="meal",
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, category="accommodation"),
            on_date=ON_DATE,
        )
        assert result.resolved is False
        assert result.unresolved_reasons
        assert result.policy_version_id is None

    def test_a_claim_with_no_category_does_not_match_a_category_assignment(
        self, db: Session
    ) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="resolve-absent-category")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.EXPENSE_CATEGORY,
            scope_key="meal",
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, category=None),
            on_date=ON_DATE,
        )
        assert result.resolved is False

    def test_an_unapproved_assignment_is_ignored(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="resolve-unapproved")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.EXPENSE_CATEGORY,
            scope_key="meal",
            approval_state="pending",
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, category="meal"),
            on_date=ON_DATE,
        )
        assert result.resolved is False

    def test_two_approved_versions_at_equal_scope_are_reported_as_a_conflict(
        self, db: Session
    ) -> None:
        """Precedence is configuration. A conflict is reported, never tie-broken."""
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        first = _insert_approved_version(db, label="resolve-conflict-a")
        second = _insert_approved_version(db, label="resolve-conflict-b")
        for version_id in (first, second):
            _insert_assignment(
                db,
                organization_id=organization_id,
                policy_version_id=version_id,
                scope_type=PolicyAssignmentScopeType.EXPENSE_CATEGORY,
                scope_key="meal",
                priority=0,
            )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, category="meal"),
            on_date=ON_DATE,
        )
        assert result.resolved is False
        assert any("precedence is not configured" in reason for reason in result.unresolved_reasons)

    def test_a_different_higher_priority_version_is_not_merged_silently(self, db: Session) -> None:
        # Two different versions at different priorities is still two versions. The
        # resolver reports the conflict; it does not treat priority as a tie-break
        # across versions, because that would be inventing precedence.
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        first = _insert_approved_version(db, label="resolve-priority-a")
        second = _insert_approved_version(db, label="resolve-priority-b")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=first,
            scope_type=PolicyAssignmentScopeType.JURISDICTION,
            scope_key="IN-MH",
            priority=10,
        )
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=second,
            scope_type=PolicyAssignmentScopeType.EXPENSE_CATEGORY,
            scope_key="meal",
            priority=20,
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, category="meal", jurisdiction="IN-MH"),
            on_date=ON_DATE,
        )
        assert result.resolved is False
        assert any("precedence is not configured" in reason for reason in result.unresolved_reasons)

    def test_an_out_of_period_assignment_does_not_apply(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        version_id = _insert_approved_version(db, label="resolve-out-of-period")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.EXPENSE_CATEGORY,
            scope_key="meal",
            effective_from=dt.date(2027, 1, 1),
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, category="meal"),
            on_date=ON_DATE,
        )
        assert result.resolved is False

    def test_a_missing_transaction_date_is_unresolved(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction=None, legal_entity=None)
        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, category="meal"),
            on_date=None,
        )
        assert result.resolved is False
        assert any("no reliable transaction date" in reason for reason in result.unresolved_reasons)

    def test_one_version_behind_two_scopes_resolves_and_reports_both(self, db: Session) -> None:
        organization_id = _insert_organization(db, jurisdiction="IN-MH", legal_entity=None)
        version_id = _insert_approved_version(db, label="resolve-two-scopes-one-version")
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.JURISDICTION,
            scope_key="IN-MH",
        )
        _insert_assignment(
            db,
            organization_id=organization_id,
            policy_version_id=version_id,
            scope_type=PolicyAssignmentScopeType.EXPENSE_CATEGORY,
            scope_key="meal",
        )
        db.flush()

        result = resolve_effective_policy(
            db,
            organization_id=organization_id,
            scope=_scope(organization_id, category="meal", jurisdiction="IN-MH"),
            on_date=ON_DATE,
        )
        assert result.resolved is True
        assert result.policy_version_id == version_id
        applied = {a.scope_type for a in result.applied_assignments}
        assert applied == {"jurisdiction", "expense_category"}
