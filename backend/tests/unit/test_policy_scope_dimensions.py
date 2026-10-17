"""Regression tests for policy-assignment scope matching.

THE DEFECT THESE TESTS EXIST FOR
--------------------------------
``policy_assignments.scope_id`` is a UUID, and every scope dimension used it. Three of
the ten supported dimensions are not UUID-valued:

* ``expense_category`` -- free text on the claim, e.g. "meal". The resolver compared
  ``str(scope_id)`` against the category, so a category assignment could **never**
  match. It looked configured and did nothing.
* ``jurisdiction`` and ``legal_entity`` -- text values recorded on the organization.
  Both returned ``False`` unconditionally, so a jurisdiction- or legal-entity-scoped
  assignment also never applied.

These tests cover every supported dimension so the same class of defect cannot come
back through a dimension nobody thought to check. The matching matrix is parametrised
over ``PolicyAssignmentScopeType`` itself, and a test asserts that the UUID/text
classification is exhaustive -- so adding a dimension without classifying it fails the
suite rather than silently never matching.

These tests deliberately assert nothing about *precedence*. Precedence is
configuration, not an assumption, and no reimbursement rule or threshold appears here.
"""

from __future__ import annotations

import uuid

import pytest
from app.core.enums import (
    TEXT_VALUED_SCOPE_TYPES,
    UUID_VALUED_SCOPE_TYPES,
    PolicyAssignmentScopeType,
    scope_selector_kind,
)
from app.models.policy import PolicyAssignment
from app.policy.base import EvaluationScope
from app.policy.resolution import _matches

pytestmark = pytest.mark.unit

ORGANIZATION_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
MEMBERSHIP_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
OFFICE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a3")
DEPARTMENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a4")
COST_CENTER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a5")
JOB_GRADE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a6")
TRIP_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a7")

JURISDICTION = "IN-MH"
LEGAL_ENTITY = "Example Consulting Pvt Ltd"
CATEGORY = "meal"


@pytest.fixture
def scope() -> EvaluationScope:
    """A scope with every supported dimension populated.

    Populated deliberately: a dimension left as None here would make a
    "does it match?" assertion pass for the wrong reason.
    """
    return EvaluationScope(
        organization_id=ORGANIZATION_ID,
        membership_id=MEMBERSHIP_ID,
        office_location_id=OFFICE_ID,
        department_id=DEPARTMENT_ID,
        cost_center_id=COST_CENTER_ID,
        job_grade_id=JOB_GRADE_ID,
        jurisdiction_code=JURISDICTION,
        legal_entity_name=LEGAL_ENTITY,
        trip_id=TRIP_ID,
        category=CATEGORY,
    )


def _assignment(
    scope_type: PolicyAssignmentScopeType,
    *,
    scope_id: uuid.UUID | None = None,
    scope_key: str | None = None,
    priority: int = 0,
) -> PolicyAssignment:
    """Build an in-memory assignment.

    Constructed rather than inserted: this tests the matching logic, and the database
    would (correctly) refuse several of the deliberately malformed combinations used
    below. The database's own refusals are covered in
    tests/integration/test_policy_assignment_scope.py.
    """
    return PolicyAssignment(
        id=uuid.uuid4(),
        organization_id=ORGANIZATION_ID,
        policy_version_id=uuid.uuid4(),
        scope_type=scope_type.value,
        scope_id=scope_id,
        scope_key=scope_key,
        priority=priority,
        approval_state="approved",
    )


# Each dimension mapped to the value this claim presents for it, and a different
# value that must NOT match.
_MATCHING_SELECTOR: dict[PolicyAssignmentScopeType, dict[str, object]] = {
    PolicyAssignmentScopeType.ORGANIZATION: {"scope_id": ORGANIZATION_ID},
    PolicyAssignmentScopeType.OFFICE_LOCATION: {"scope_id": OFFICE_ID},
    PolicyAssignmentScopeType.DEPARTMENT: {"scope_id": DEPARTMENT_ID},
    PolicyAssignmentScopeType.COST_CENTER: {"scope_id": COST_CENTER_ID},
    PolicyAssignmentScopeType.JOB_GRADE: {"scope_id": JOB_GRADE_ID},
    PolicyAssignmentScopeType.TRIP: {"scope_id": TRIP_ID},
    PolicyAssignmentScopeType.EMPLOYEE: {"scope_id": MEMBERSHIP_ID},
    PolicyAssignmentScopeType.JURISDICTION: {"scope_key": JURISDICTION},
    PolicyAssignmentScopeType.LEGAL_ENTITY: {"scope_key": LEGAL_ENTITY},
    PolicyAssignmentScopeType.EXPENSE_CATEGORY: {"scope_key": CATEGORY},
}


class TestScopeClassification:
    """The UUID/text split is the single source of truth; it must stay total."""

    def test_every_dimension_is_classified(self) -> None:
        classified = UUID_VALUED_SCOPE_TYPES | TEXT_VALUED_SCOPE_TYPES
        unclassified = set(PolicyAssignmentScopeType) - classified
        assert unclassified == set(), (
            "these scope dimensions are classified neither UUID-valued nor text-valued, so "
            "they can never be matched: "
            f"{sorted(member.value for member in unclassified)}. Add each to "
            "UUID_VALUED_SCOPE_TYPES or TEXT_VALUED_SCOPE_TYPES in app/core/enums.py."
        )

    def test_no_dimension_is_classified_twice(self) -> None:
        overlap = UUID_VALUED_SCOPE_TYPES & TEXT_VALUED_SCOPE_TYPES
        assert overlap == set(), "a dimension cannot be both UUID-valued and text-valued"

    def test_the_matching_selector_map_covers_every_classified_dimension(self) -> None:
        # Guards this test module itself: a new dimension must be given a case here,
        # not skipped silently.
        assert set(_MATCHING_SELECTOR) == set(PolicyAssignmentScopeType)

    @pytest.mark.parametrize("scope_type", list(PolicyAssignmentScopeType))
    def test_selector_kind_agrees_with_the_sets(
        self, scope_type: PolicyAssignmentScopeType
    ) -> None:
        expected = "uuid" if scope_type in UUID_VALUED_SCOPE_TYPES else "text"
        assert scope_selector_kind(scope_type) == expected
        # Accepts the raw string form too, which is what the database stores.
        assert scope_selector_kind(scope_type.value) == expected

    def test_an_unknown_dimension_raises_rather_than_never_matching(self) -> None:
        with pytest.raises(ValueError, match="unknown policy assignment scope type"):
            scope_selector_kind("employee_band_v2")


class TestEveryDimensionMatches:
    """Parametrised over the enum, so no dimension is left untested."""

    @pytest.mark.parametrize("scope_type", list(PolicyAssignmentScopeType))
    def test_a_matching_assignment_applies(
        self, scope_type: PolicyAssignmentScopeType, scope: EvaluationScope
    ) -> None:
        assignment = _assignment(scope_type, **_MATCHING_SELECTOR[scope_type])
        assert _matches(assignment, scope) is True

    @pytest.mark.parametrize("scope_type", list(PolicyAssignmentScopeType))
    def test_a_non_matching_assignment_does_not_apply(
        self, scope_type: PolicyAssignmentScopeType, scope: EvaluationScope
    ) -> None:
        selector = dict(_MATCHING_SELECTOR[scope_type])
        if "scope_id" in selector:
            selector["scope_id"] = uuid.uuid4()
        else:
            selector["scope_key"] = "some-other-value"
        assignment = _assignment(scope_type, **selector)
        assert _matches(assignment, scope) is False


class TestExpenseCategoryRegression:
    """The specific defect: a category assignment could never match."""

    def test_a_category_assignment_matches_on_its_text_key(self, scope: EvaluationScope) -> None:
        assignment = _assignment(PolicyAssignmentScopeType.EXPENSE_CATEGORY, scope_key=CATEGORY)
        assert _matches(assignment, scope) is True

    def test_a_different_category_does_not_match(self, scope: EvaluationScope) -> None:
        assignment = _assignment(
            PolicyAssignmentScopeType.EXPENSE_CATEGORY, scope_key="accommodation"
        )
        assert _matches(assignment, scope) is False

    def test_a_uuid_selector_can_no_longer_edge_a_category_match(
        self, scope: EvaluationScope
    ) -> None:
        """The old behaviour, asserted to be gone.

        Previously the resolver compared ``str(scope_id)`` against the category. A
        category is free text, so such an assignment stored a UUID and could never
        match. The database now refuses to store that shape
        (ck_policy_assignments_scope_selector_consistent); this asserts the resolver
        would not match it even if one existed.
        """
        malformed = _assignment(
            PolicyAssignmentScopeType.EXPENSE_CATEGORY,
            scope_id=uuid.uuid4(),
            scope_key=None,
        )
        assert _matches(malformed, scope) is False

    def test_a_category_that_looks_like_a_uuid_is_still_compared_as_text(
        self, scope: EvaluationScope
    ) -> None:
        # A category could in principle be any string. It must be compared as text
        # against the text key, never coerced into a UUID.
        uuid_like = "00000000-0000-4000-8000-000000000abc"
        targeted = EvaluationScope(
            organization_id=ORGANIZATION_ID,
            membership_id=MEMBERSHIP_ID,
            category=uuid_like,
        )
        assignment = _assignment(PolicyAssignmentScopeType.EXPENSE_CATEGORY, scope_key=uuid_like)
        assert _matches(assignment, targeted) is True


class TestJurisdictionAndLegalEntity:
    """Both dimensions previously returned False unconditionally."""

    def test_a_jurisdiction_assignment_now_resolves(self, scope: EvaluationScope) -> None:
        assignment = _assignment(PolicyAssignmentScopeType.JURISDICTION, scope_key=JURISDICTION)
        assert _matches(assignment, scope) is True

    def test_a_legal_entity_assignment_now_resolves(self, scope: EvaluationScope) -> None:
        assignment = _assignment(PolicyAssignmentScopeType.LEGAL_ENTITY, scope_key=LEGAL_ENTITY)
        assert _matches(assignment, scope) is True

    def test_a_different_jurisdiction_does_not_resolve(self, scope: EvaluationScope) -> None:
        assignment = _assignment(PolicyAssignmentScopeType.JURISDICTION, scope_key="IN-KA")
        assert _matches(assignment, scope) is False

    def test_a_different_legal_entity_does_not_resolve(self, scope: EvaluationScope) -> None:
        assignment = _assignment(
            PolicyAssignmentScopeType.LEGAL_ENTITY, scope_key="Other Entity Ltd"
        )
        assert _matches(assignment, scope) is False


class TestTextSelectorNormalisation:
    """Case and whitespace are normalised; nothing else is."""

    @pytest.mark.parametrize(
        "assignment_key",
        ["in-mh", "IN-MH", "In-Mh", "  IN-MH  "],
    )
    def test_case_and_whitespace_do_not_change_a_jurisdiction_match(
        self, assignment_key: str, scope: EvaluationScope
    ) -> None:
        assignment = _assignment(PolicyAssignmentScopeType.JURISDICTION, scope_key=assignment_key)
        assert _matches(assignment, scope) is True

    def test_a_different_code_is_not_folded_into_a_match(self, scope: EvaluationScope) -> None:
        # Normalisation must not become fuzzy matching.
        for other in ["IN", "IN-MH-01", "IN MH", "MH"]:
            assignment = _assignment(PolicyAssignmentScopeType.JURISDICTION, scope_key=other)
            assert _matches(assignment, scope) is False, other

    def test_a_blank_key_cannot_be_constructed_at_all(self) -> None:
        """A blank key is now refused before it can reach the matcher.

        Previously a blank key could exist and simply never matched anything -- an
        assignment that looked configured and silently did nothing. It is now refused at
        construction by the model validator, and independently by the database CHECK.
        """
        from app.core.scope_keys import BlankScopeKeyError

        with pytest.raises(BlankScopeKeyError):
            _assignment(PolicyAssignmentScopeType.EXPENSE_CATEGORY, scope_key="   ")

    def test_a_claim_whose_category_is_blank_still_matches_nothing(
        self, scope: EvaluationScope
    ) -> None:
        # The read path stays permissive: a claim with no usable category value has no
        # value for the dimension, so it matches no assignment. That is not an error and
        # must not raise.
        assignment = _assignment(PolicyAssignmentScopeType.EXPENSE_CATEGORY, scope_key="meal")
        blank_claim = EvaluationScope(
            organization_id=ORGANIZATION_ID, membership_id=MEMBERSHIP_ID, category="   "
        )
        assert _matches(assignment, blank_claim) is False


class TestAbsentDimensionNeverMatches:
    """A dimension the claim has no value for cannot satisfy an assignment."""

    @pytest.mark.parametrize(
        ("scope_type", "selector"),
        [
            (PolicyAssignmentScopeType.TRIP, {"scope_id": TRIP_ID}),
            (PolicyAssignmentScopeType.OFFICE_LOCATION, {"scope_id": OFFICE_ID}),
            (PolicyAssignmentScopeType.DEPARTMENT, {"scope_id": DEPARTMENT_ID}),
            (PolicyAssignmentScopeType.COST_CENTER, {"scope_id": COST_CENTER_ID}),
            (PolicyAssignmentScopeType.JOB_GRADE, {"scope_id": JOB_GRADE_ID}),
            (PolicyAssignmentScopeType.EXPENSE_CATEGORY, {"scope_key": CATEGORY}),
            (PolicyAssignmentScopeType.JURISDICTION, {"scope_key": JURISDICTION}),
            (PolicyAssignmentScopeType.LEGAL_ENTITY, {"scope_key": LEGAL_ENTITY}),
        ],
    )
    def test_an_optional_dimension_that_is_absent_does_not_match(
        self, scope_type: PolicyAssignmentScopeType, selector: dict[str, object]
    ) -> None:
        bare = EvaluationScope(organization_id=ORGANIZATION_ID, membership_id=MEMBERSHIP_ID)
        assignment = _assignment(scope_type, **selector)
        assert _matches(assignment, bare) is False

    def test_organization_scope_always_matches_its_own_claim(self, scope: EvaluationScope) -> None:
        # The only dimension every claim necessarily has.
        assignment = _assignment(PolicyAssignmentScopeType.ORGANIZATION, scope_id=ORGANIZATION_ID)
        assert _matches(assignment, scope) is True
