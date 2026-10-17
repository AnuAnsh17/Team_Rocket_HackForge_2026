"""The text scope key normalization contract.

This file pins the contract in three directions, because the defect it was written for
came from the contract existing in two places at once:

* **Against Python's own definition.** The whitespace set must equal exactly
  ``{chr(c) for c in range(0x10000) if chr(c).isspace()}``. Writing the set out by hand
  is what makes it usable from SQL; this test is what stops it drifting from Python.
* **Against the database.** The migration's SQL is frozen and cannot import live code,
  so it carries a copy. A test here asserts the copy still equals the live expression.
* **Against itself.** Canonicalization must be idempotent, or a stored key could be
  normalized on read and come out different from how it went in.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from app.core.scope_keys import (
    MAX_CANONICAL_SCOPE_KEY_LENGTH,
    SCOPE_KEY_WHITESPACE,
    BlankScopeKeyError,
    canonical_form_sql,
    canonical_match_key,
    is_canonical_scope_key,
    normalize_scope_key,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# The whitespace set is pinned to Python's definition
# ---------------------------------------------------------------------------


class TestWhitespaceSet:
    def test_it_equals_pythons_own_whitespace_definition(self) -> None:
        # Python's whitespace characters are all within the BMP, so scanning it is a
        # complete check rather than a sample.
        pythons = {chr(codepoint) for codepoint in range(0x10000) if chr(codepoint).isspace()}
        assert set(SCOPE_KEY_WHITESPACE) == pythons, (
            "SCOPE_KEY_WHITESPACE no longer matches str.isspace(). The database applies a "
            "frozen copy of this set, so it must be updated in a NEW migration as well - "
            "and this failure is the reminder."
        )

    def test_it_has_no_duplicates(self) -> None:
        assert len(SCOPE_KEY_WHITESPACE) == len(set(SCOPE_KEY_WHITESPACE))

    @pytest.mark.parametrize(
        "character",
        [
            "\t",
            "\n",
            "\r",
            "\x0b",
            "\x0c",
            " ",
            "\xa0",
            "\u1680",
            "\u2000",
            "\u2003",
            "\u2028",
            "\u202f",
            "\u205f",
            "\u3000",
            "\x1c",
            "\x85",
        ],
    )
    def test_representative_characters_are_treated_as_whitespace(self, character: str) -> None:
        assert canonical_match_key(f"in{character}mh{character}") == "in mh"


# ---------------------------------------------------------------------------
# Canonical form
# ---------------------------------------------------------------------------


class TestCanonicalForm:
    @pytest.mark.parametrize(
        "raw",
        ["in-mh", "IN-MH", "In-Mh", " in-mh ", "\tin-mh\n", "  IN-MH  ", "in-mh\xa0"],
    )
    def test_case_and_whitespace_variants_collapse_to_one_key(self, raw: str) -> None:
        # The whole point: these are one key to the resolver, so they must be one key to
        # the database's unique index too.
        assert canonical_match_key(raw) == "in-mh"

    def test_internal_whitespace_runs_collapse_to_a_single_space(self) -> None:
        assert canonical_match_key("in\t\tmh") == "in mh"
        assert canonical_match_key("in   mh") == "in mh"

    def test_it_does_not_fuzzy_match(self) -> None:
        # Normalization must not become fuzzy matching.
        for other in ["in mh", "inmh", "in-mh-01", "in", "mh", "in--mh"]:
            assert canonical_match_key(other) != "in-mh", other

    def test_it_uses_casefold_not_lower(self) -> None:
        """The operation matters, and this is the case where it is observable.

        ``"straße".lower()`` is ``"straße"``; ``"straße".casefold()`` is ``"strasse"``.
        Case folding is the Unicode operation for caseless comparison, and a legal entity
        name is exactly the kind of value that contains such a character.
        """
        assert "straße".lower() != "strasse"
        assert canonical_match_key("straße") == "strasse"
        assert canonical_match_key("STRASSE") == "strasse"

    @pytest.mark.parametrize(
        "raw",
        ["in-mh", "in  mh", " in-mh ", "stra\u00dfe", "a\xa0b", "in\u3000mh", "MixEd Case"],
    )
    def test_it_is_idempotent(self, raw: str) -> None:
        once = canonical_match_key(raw)
        assert once is not None
        assert canonical_match_key(once) == once
        assert is_canonical_scope_key(once) is True


# ---------------------------------------------------------------------------
# Blank keys: the write path refuses, the read path returns absence
# ---------------------------------------------------------------------------


class TestBlankKeys:
    @pytest.mark.parametrize("blank", ["", " ", "   ", "\t", "\n", "\xa0", " \t\n\xa0 "])
    def test_the_write_path_refuses_a_blank_key(self, blank: str) -> None:
        """A key that normalizes to nothing can never match a claim.

        Storing one would create an assignment that looks configured and never applies,
        so it is refused rather than stored.
        """
        with pytest.raises(BlankScopeKeyError, match="at least one non-whitespace"):
            normalize_scope_key(blank)

    @pytest.mark.parametrize("blank", ["", " ", "\t", "\xa0"])
    def test_the_read_path_reports_absence_instead_of_raising(self, blank: str) -> None:
        # A claim whose category is blank simply has no value for that dimension. That is
        # not an error, it is a claim that matches no assignment.
        assert canonical_match_key(blank) is None

    def test_none_passes_through_both_paths(self) -> None:
        assert normalize_scope_key(None) is None
        assert canonical_match_key(None) is None

    def test_blank_scope_keys_are_not_canonical(self) -> None:
        assert is_canonical_scope_key("") is False
        assert is_canonical_scope_key(None) is False
        assert is_canonical_scope_key(" ") is False


class TestCanonicalWritePath:
    def test_a_valid_key_is_normalized_on_the_way_in(self) -> None:
        assert normalize_scope_key(" IN-MH ") == "in-mh"

    def test_an_over_long_key_is_refused_in_python_before_the_database(self) -> None:
        # The stored column is VARCHAR(200); a key that cannot be stored is not a key,
        # and failing here is legible rather than a driver error.
        with pytest.raises(ValueError, match="at most"):
            normalize_scope_key("x" * (MAX_CANONICAL_SCOPE_KEY_LENGTH + 1))

    def test_a_key_at_the_limit_is_accepted(self) -> None:
        assert len(normalize_scope_key("x" * MAX_CANONICAL_SCOPE_KEY_LENGTH) or "") == (
            MAX_CANONICAL_SCOPE_KEY_LENGTH
        )


class TestModelValidator:
    """The ORM is the write path, so it must store canonical keys."""

    def test_assigning_a_key_normalizes_it(self) -> None:
        from app.models.policy import PolicyAssignment

        assignment = PolicyAssignment(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            policy_version_id=uuid.uuid4(),
            scope_type="jurisdiction",
            scope_key="  IN-MH  ",
            priority=0,
            approval_state="approved",
        )
        assert assignment.scope_key == "in-mh"

    def test_assigning_a_blank_key_raises(self) -> None:
        from app.models.policy import PolicyAssignment

        with pytest.raises(BlankScopeKeyError):
            PolicyAssignment(
                id=uuid.uuid4(),
                organization_id=uuid.uuid4(),
                policy_version_id=uuid.uuid4(),
                scope_type="jurisdiction",
                scope_key="   ",
                priority=0,
                approval_state="approved",
            )


# ---------------------------------------------------------------------------
# The database's copy must still be the same rule
# ---------------------------------------------------------------------------


class TestMigrationParity:
    """Migrations are frozen, so their SQL is a copy. Copies drift; this catches it."""

    @staticmethod
    def _load_migration():
        path = (
            Path(__file__).resolve().parents[2]
            / "migrations"
            / "versions"
            / "0003_scope_key_canonical.py"
        )
        spec = importlib.util.spec_from_file_location("_mig_0003", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_the_migration_uses_the_same_canonical_expression(self) -> None:
        migration = self._load_migration()
        assert canonical_form_sql("scope_key") == migration._CANONICAL_FORM_SQL, (
            "the migration's frozen SQL no longer matches app/core/scope_keys.py. Do not "
            "edit an applied migration: add a new one that replaces the constraint, and "
            "update this expectation with it."
        )

    def test_the_migration_uses_the_same_whitespace_set(self) -> None:
        migration = self._load_migration()
        assert migration._WHITESPACE_CHARS == SCOPE_KEY_WHITESPACE

    def test_the_migration_guards_before_it_touches_any_data(self) -> None:
        """Both guards are what make the migration safe on populated data.

        One refuses a key that could never match; the other refuses to collapse two
        assignments into one without a human deciding which survives. Both must run
        BEFORE the backfill, or the migration would rewrite keys and only then discover
        it cannot proceed.

        Scoped to the body of ``upgrade()``: the function definitions appear earlier in
        the file, so searching the whole source would compare the wrong things.
        """
        source = (
            Path(__file__).resolve().parents[2]
            / "migrations"
            / "versions"
            / "0003_scope_key_canonical.py"
        ).read_text(encoding="utf-8")
        upgrade_body = source.split("def upgrade() -> None:", 1)[1].split("def downgrade", 1)[0]

        assert "_assert_no_blank_keys()" in upgrade_body
        assert "_assert_no_collisions()" in upgrade_body
        assert "_backfill_canonical_keys()" in upgrade_body
        assert upgrade_body.index("_assert_no_blank_keys()") < upgrade_body.index(
            "_backfill_canonical_keys()"
        )
        assert upgrade_body.index("_assert_no_collisions()") < upgrade_body.index(
            "_backfill_canonical_keys()"
        )
        assert upgrade_body.index("_backfill_canonical_keys()") < upgrade_body.index(
            "_NEW_UNIQUE_INDEX"
        )
