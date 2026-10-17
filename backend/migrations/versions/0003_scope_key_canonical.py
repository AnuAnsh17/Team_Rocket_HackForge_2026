"""canonical scope keys: align uniqueness with the resolver

Revision ID: 0003_scope_key_canonical
Revises: 0002_scope_selector
Created: 2026-10-17

WHY THIS MIGRATION EXISTS
-------------------------
The resolver normalized a text scope key with ``str.strip().casefold()`` while the unique
index from 0002 used ``lower(COALESCE(scope_key, ''))``. Different functions, so:

* ``"in-mh"`` and ``" in-mh "`` could BOTH be stored, even though the resolver treats
  them as the same key. Two assignments the resolver considered identical could coexist,
  and the resolution would depend on row order -- or be reported as a conflict.
* Unicode case folding (Python) is not lowercasing (PostgreSQL, locale-dependent). They
  differ for real input: ``"ß".casefold() == "ss"`` but ``"ß".lower() == "ß"``.

The fix is not to reimplement case folding in SQL. It is to make the
stored value the canonical value, so that uniqueness and matching operate on the same
string by construction. The contract lives in ``app/core/scope_keys.py``.

WHAT THIS MIGRATION DOES
------------------------
1. Backfills ``scope_key`` to a canonical form for existing text-dimension rows.
2. Adds ``ck_policy_assignments_scope_key_canonical``: a text selector must be
   non-blank, have no surrounding whitespace, and already be lowercased. A blank key
   can never match a claim, so storing one would create an assignment that looks
   configured and never applies.
3. Replaces the functional unique index with one over the canonical column itself, so
   there is no second normalization function to disagree with the resolver.

PostgreSQL cannot compute ``casefold()``, so step 1 uses ``lower(btrim(...))`` -- the
closest exact-equivalent operation available. The residual is stated rather than hidden
in ``app/core/scope_keys.py``: matching canonicalizes both sides, so a row that slipped
in non-canonically still matches correctly rather than becoming inert, and if it
coexists with a canonical twin the outcome is a reported resolution conflict rather
than a silent duplicate.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
No precedence, thresholds, approval stages or reimbursement rules. It does not touch any
other table, any hand-written integrity index, or the append-only audit trigger.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_scope_key_canonical"
down_revision: str | None = "0002_scope_selector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEXT_SCOPE_TYPES = "('expense_category', 'jurisdiction', 'legal_entity')"

# Uniqueness over the canonical column. No lower() and no btrim(): the CHECK below
# guarantees the stored value is already canonical, so applying a second normalization
# here is precisely the drift this migration removes.
_NEW_UNIQUE_INDEX = (
    "CREATE UNIQUE INDEX uq_policy_assignments_scope_selector "
    "ON policy_assignments ("
    "    organization_id,"
    "    policy_version_id,"
    "    scope_type,"
    "    COALESCE(scope_id::text, ''),"
    "    COALESCE(scope_key, '')"
    ")"
)

# The index from 0002, restored verbatim on downgrade.
_OLD_UNIQUE_INDEX = (
    "CREATE UNIQUE INDEX uq_policy_assignments_scope_selector "
    "ON policy_assignments ("
    "    organization_id,"
    "    policy_version_id,"
    "    scope_type,"
    "    COALESCE(scope_id::text, ''),"
    "    lower(COALESCE(scope_key, ''))"
    ")"
)

# The whitespace characters the application trims and collapses. This literal MUST stay
# identical to app/core/scope_keys.py::SCOPE_KEY_WHITESPACE, which a unit test pins to
# exactly Python's str.isspace() definition.
#
# Why the characters are listed rather than using btrim()'s default: PostgreSQL's plain
# btrim(scope_key) trims only the space character, while the application trims all of
# these. Using the default would leave a non-breaking space in place, so "in-mh\u00a0"
# could be stored alongside "in-mh" even though the resolver treats them as one key --
# the very mismatch this migration exists to remove. A migration is frozen code, so if
# that shared set ever changes this literal must change with it, in a new migration.
_WHITESPACE_CHARS = (
    "\t\n\x0b\x0c\r "
    "\x1c\x1d\x1e\x1f"
    "\x85\xa0"
    "\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)

# A single equation rather than three separate conditions: the stored key must equal its
# own canonical form. That enforces trimming, collapsing and lowercasing together, so a
# future edit cannot drop one of the three and leave the others looking correct.
#
# ``scope_key <> ''`` is separate because the equation alone would accept an empty
# string ('' equals its own canonical form), and a blank key can never match a claim.
#
# ``lower()`` is PostgreSQL's operation, not Python's casefold(). They agree for the
# cases that occur here and differ for a few characters ("\u00df" folds to "ss");
# matching canonicalizes both sides, so the consequence of that residue is a reported
# conflict rather than a silent duplicate. See app/core/scope_keys.py.
_CANONICAL_FORM_SQL = (
    "lower("
    "regexp_replace("
    f"btrim(scope_key, '{_WHITESPACE_CHARS}'),"
    f" '[{_WHITESPACE_CHARS}]+',"
    " ' ',"
    " 'g'"
    ")"
    ")"
)

_CANONICAL_CHECK = (
    "("
    f"  scope_type NOT IN {_TEXT_SCOPE_TYPES}"
    "  OR ("
    "    scope_key IS NOT NULL"
    "    AND scope_key <> ''"
    f"    AND scope_key = {_CANONICAL_FORM_SQL}"
    "  )"
    ")"
)


def _backfill_canonical_keys() -> None:
    """Canonicalise existing text scope keys.

    Uses the same expression as the CHECK constraint above, so the backfill cannot
    produce a value the constraint would then reject. Whitespace is handled exactly
    (both sides use the shared character list); the case dimension uses PostgreSQL's
    ``lower()``, the closest operation available in SQL to Python's ``casefold()``.
    """
    op.execute(
        f"""
        UPDATE policy_assignments
        SET scope_key = {_CANONICAL_FORM_SQL}
        WHERE scope_type IN {_TEXT_SCOPE_TYPES}
          AND scope_key IS NOT NULL
        """
    )


def _assert_no_blank_keys() -> None:
    """Refuse to proceed if a key would normalize to nothing.

    Raising a legible error beats letting the CHECK constraint fail with a generated
    name: an operator needs to know a row must be fixed, not which constraint tripped.
    """
    op.execute(
        f"""
        DO $$
        DECLARE offending uuid;
        BEGIN
            SELECT id INTO offending
            FROM policy_assignments
            WHERE scope_type IN {_TEXT_SCOPE_TYPES}
              AND (scope_key IS NULL OR btrim(scope_key) = '')
            LIMIT 1;

            IF offending IS NOT NULL THEN
                RAISE EXCEPTION
                    'cannot add ck_policy_assignments_scope_key_canonical: policy assignment '
                    '% has a blank text scope key, which can never match a claim. Correct or '
                    'delete that row and re-run; this migration will not guess a key for you.',
                    offending;
            END IF;
        END
        $$;
        """
    )


def _assert_no_collisions() -> None:
    """Refuse to proceed if canonicalising would collapse two rows into one.

    Better to stop and let a human decide which assignment survives than to let the
    unique index fail, or silently drop one.
    """
    op.execute(
        """
        DO $$
        DECLARE conflicting text;
        BEGIN
            SELECT string_agg(scope_type || '=' || COALESCE(scope_key, ''), ', ')
              INTO conflicting
            FROM (
                SELECT scope_type, scope_key
                FROM policy_assignments
                WHERE scope_type IN ('expense_category', 'jurisdiction', 'legal_entity')
                GROUP BY organization_id, policy_version_id, scope_type, scope_key
                HAVING count(*) > 1
            ) AS duplicates;

            IF conflicting IS NOT NULL THEN
                RAISE EXCEPTION
                    'cannot add the canonical unique index: these text scope keys are '
                    'already duplicated for the same policy version: %. Review them before '
                    're-running this migration.', conflicting;
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _assert_no_blank_keys()
    _assert_no_collisions()
    _backfill_canonical_keys()

    op.create_check_constraint(
        "scope_key_canonical",
        "policy_assignments",
        _CANONICAL_CHECK,
    )

    op.execute("DROP INDEX IF EXISTS uq_policy_assignments_scope_selector")
    op.execute(_NEW_UNIQUE_INDEX)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_policy_assignments_scope_selector")
    op.execute(_OLD_UNIQUE_INDEX)

    # Explicit DDL: the MetaData naming convention is re-applied to op.drop_constraint,
    # which would produce ck_policy_assignments_ck_policy_assignments_scope_key_... .
    op.execute(
        "ALTER TABLE policy_assignments DROP CONSTRAINT ck_policy_assignments_scope_key_canonical"
    )

    # Stored keys are left canonical on downgrade. The old schema permitted any case, so
    # canonical values remain valid; re-introducing the non-canonical forms we just
    # removed would recreate the duplicate-key hazard for no benefit.
