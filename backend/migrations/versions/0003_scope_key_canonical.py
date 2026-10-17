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
  differ for real input: ``"Stra\u00dfe".casefold() == "strasse"`` while
  ``"Stra\u00dfe".lower() == "stra\u00dfe"``. So ``"Stra\u00dfe"`` and ``"STRASSE"``
  are two distinct keys to PostgreSQL but one key to the resolver.

The fix is not to reimplement case folding in SQL. It is to make the stored value the
canonical value, so that uniqueness and matching operate on the same string by
construction. The contract lives in ``app/core/scope_keys.py``.

WHAT THIS MIGRATION DOES
------------------------
1. Refuses, **before modifying anything**, three classes of unsafe legacy row:
   a. a text scope key that is blank under the contract (including tab-only,
      non-breaking-space-only and other Unicode-whitespace-only keys, which a default
      ``btrim()`` does NOT catch);
   b. a key that would exceed the column width once canonicalised (case folding can
      expand a string: ``"\u00df" -> "ss"``);
   c. two or more rows in the same (organization, policy version, scope type) whose keys
      would collapse to the SAME canonical value -- reported with the affected assignment
      ids and the original keys. It does not delete a row and does not pick a winner.
2. Canonicalises the surviving keys with a frozen copy of the contract, and verifies the
   result against the exact SQL expression of the new constraint.
3. Adds ``ck_policy_assignments_scope_key_canonical`` and replaces the functional unique
   index with one over the canonical column itself.

WHY A FROZEN COPY RATHER THAN AN IMPORT
---------------------------------------
A migration is history: an applied revision must keep meaning what it meant when it ran.
Importing ``app.core.scope_keys`` would make this file's behaviour change whenever the
live contract changes, and re-running it against an old database would then produce
different data than it did the first time. So the canonicalisation is copied verbatim into
this module, with the whitespace characters written out, and a unit test pins the copy to
the live contract (``tests/unit/test_scope_keys.py::TestMigrationParity``).

The preflight and backfill use that Python copy, NOT PostgreSQL's ``lower()`` -- which is
the whole point. An earlier revision of this migration used ``lower()`` for both, so a
``"Stra\u00dfe"``/``"STRASSE"`` pair was neither detected as a collision nor converged to
the same key, and the migration would have silently produced exactly the duplicate the fix
exists to prevent.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
No precedence, thresholds, approval stages or reimbursement rules. It does not touch any
other table, any hand-written integrity index, or the append-only audit trigger.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_scope_key_canonical"
down_revision: str | None = "0002_scope_selector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Dimensions whose selector is a text key rather than a UUID. Duplicated from
# app/core/enums.py for the same reason the canonicalisation is: this file is frozen.
_TEXT_SCOPE_TYPE_VALUES = ("expense_category", "jurisdiction", "legal_entity")
_TEXT_SCOPE_TYPES = "(" + ", ".join(f"'{value}'" for value in _TEXT_SCOPE_TYPE_VALUES) + ")"

# The width of policy_assignments.scope_key. A canonical key wider than this cannot be
# stored, so the migration refuses rather than letting the UPDATE fail on a driver error.
_MAX_KEY_LENGTH = 200

# The whitespace characters the application trims and collapses. Verbatim copy of
# app/core/scope_keys.py::SCOPE_KEY_WHITESPACE, which a test pins to exactly Python's
# str.isspace() definition. Listed explicitly rather than using btrim()'s default because
# PostgreSQL's plain btrim(scope_key) trims only the space character.
_WHITESPACE_CHARS = (
    "\t\n\x0b\x0c\r "
    "\x1c\x1d\x1e\x1f"
    "\x85\xa0"
    "\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)

_WHITESPACE_RUN = re.compile(f"[{re.escape(_WHITESPACE_CHARS)}]+")

# How many offending rows to name in a refusal message before summarising the rest.
_MAX_REPORTED = 20

# The SQL form of the canonical value, used by the CHECK constraint and by the
# post-backfill verification. Deliberately ``lower()``: PostgreSQL cannot compute Python's
# ``casefold()``, so this is the strongest statement the database can make on its own, and
# the backfill is what guarantees the Python contract. The verification below proves the
# two agree for the data actually present, rather than assuming it.
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

# Uniqueness over the canonical column. No lower() and no btrim(): the CHECK above
# guarantees the stored value is already canonical, so a second normalization here is
# precisely the drift this migration removes.
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

_SELECT_TEXT_KEYS = sa.text(
    f"""
    SELECT id, organization_id, policy_version_id, scope_type, scope_key
    FROM policy_assignments
    WHERE scope_type IN {_TEXT_SCOPE_TYPES}
      AND scope_key IS NOT NULL
    ORDER BY organization_id, policy_version_id, scope_type, id
    """
)


def canonical_key(raw: str) -> str:
    """The frozen canonical form of a raw text scope key.

    The contract in app/core/scope_keys.py, expressed identically: trim and collapse
    ``_WHITESPACE_CHARS``, then case-fold. Copied rather than imported on purpose -- see
    the module docstring.
    """
    return _WHITESPACE_RUN.sub(" ", raw.strip(_WHITESPACE_CHARS)).casefold()


def _describe(rows: Sequence[sa.Row]) -> str:
    """Render offending rows for a refusal message, bounded in length."""
    parts = [f"{row.id}={row.scope_key!r}" for row in rows[:_MAX_REPORTED]]
    if len(rows) > _MAX_REPORTED:
        parts.append(f"... and {len(rows) - _MAX_REPORTED} more")
    return "; ".join(parts)


def _preflight(connection: sa.Connection) -> list[sa.Row]:
    """Refuse unsafe legacy data, and return the rows that may be canonicalised.

    Runs before any DDL or DML, so a refusal leaves the database exactly as it was. Every
    check is against the canonical value this migration would actually store, not the raw
    key -- grouping by the raw key is what let ``"in-mh"`` and ``" in-mh "`` pass an earlier
    revision of this migration.
    """
    rows = list(connection.execute(_SELECT_TEXT_KEYS))

    blank: list[sa.Row] = []
    too_long: list[sa.Row] = []
    groups: dict[tuple[object, object, object, str], list[sa.Row]] = {}

    for row in rows:
        canonical = canonical_key(row.scope_key)
        if not canonical:
            # Catches tab-only, non-breaking-space-only and other Unicode-whitespace-only
            # keys, which a default btrim() would leave looking like real keys.
            blank.append(row)
            continue
        if len(canonical) > _MAX_KEY_LENGTH:
            too_long.append(row)
            continue
        groups.setdefault(
            (row.organization_id, row.policy_version_id, row.scope_type, canonical), []
        ).append(row)

    if blank:
        raise RuntimeError(
            f"cannot canonicalise policy assignment scope keys: {len(blank)} row(s) have a "
            "text scope key that is empty or whitespace-only under the application's "
            "contract, so they can never match a claim. Nothing has been modified. Correct "
            "or delete these rows and re-run: " + _describe(blank)
        )

    if too_long:
        raise RuntimeError(
            f"cannot canonicalise policy assignment scope keys: {len(too_long)} row(s) "
            f"would exceed the {_MAX_KEY_LENGTH}-character column width once canonicalised, "
            "and case folding can lengthen a string. Nothing has been modified. Shorten or "
            "delete these rows and re-run: " + _describe(too_long)
        )

    collisions = [(key, members) for key, members in groups.items() if len(members) > 1]
    if collisions:
        details = "; ".join(
            f"[{key[2]} {key[3]!r}] " + _describe(members) for key, members in collisions
        )
        raise RuntimeError(
            f"cannot canonicalise policy assignment scope keys: {len(collisions)} group(s) "
            "would collapse to the same canonical key for the same organization, policy "
            "version and scope type, so the unique index could not be built. Nothing has "
            "been modified. Review each group by hand -- this migration does not delete a "
            "row and does not choose a winner: " + details
        )

    return rows


def _backfill_canonical_keys(connection: sa.Connection, rows: Sequence[sa.Row]) -> int:
    """Rewrite text scope keys to their frozen canonical form.

    Only rows that actually change are updated, so a re-run on canonical data is a no-op.
    """
    updates = [
        (row.id, canonical_key(row.scope_key))
        for row in rows
        if row.scope_key != canonical_key(row.scope_key)
    ]
    if not updates:
        return 0

    connection.execute(
        sa.text("UPDATE policy_assignments SET scope_key = :scope_key WHERE id = :id"),
        [{"id": assignment_id, "scope_key": key} for assignment_id, key in updates],
    )
    return len(updates)


def _assert_stored_keys_satisfy_the_check(connection: sa.Connection) -> None:
    """Prove the canonicalised data satisfies the constraint before adding it.

    The constraint asks PostgreSQL whether each stored key equals its own ``lower()``
    canonical form. ``lower()`` is not ``casefold()``, so rather than assume the two agree
    on this data, this asks the database directly. A mismatch here is a real finding about
    a character in the data, and it is reported with the offending rows rather than
    surfacing as a constraint violation.
    """
    offenders = list(
        connection.execute(
            sa.text(
                f"""
                SELECT id, scope_key FROM policy_assignments
                WHERE scope_type IN {_TEXT_SCOPE_TYPES}
                  AND scope_key IS NOT NULL
                  AND (scope_key = '' OR scope_key <> {_CANONICAL_FORM_SQL})
                ORDER BY id
                """
            )
        )
    )
    if offenders:
        raise RuntimeError(
            "cannot add ck_policy_assignments_scope_key_canonical: "
            f"{len(offenders)} row(s) do not satisfy the database's canonical form after "
            "backfill. This means a character in the data is transformed differently by "
            "Python's casefold() and PostgreSQL's lower(), which the migration will not "
            "paper over. Nothing has been modified. Report these rows: " + _describe(offenders)
        )


def upgrade() -> None:
    connection = op.get_bind()

    # 1. Refuse unsafe legacy data before touching anything.
    rows = _preflight(connection)

    # 2. Drop the old functional index first: it keys on lower(scope_key), and leaving it
    #    in place during the rewrite would make the UPDATE re-check an index that is about
    #    to be replaced -- a transient conflict surface this ordering removes entirely.
    op.execute("DROP INDEX IF EXISTS uq_policy_assignments_scope_selector")

    # 3. Canonicalise, using the frozen Python contract rather than lower().
    _backfill_canonical_keys(connection, rows)

    # 4. Prove the result satisfies the constraint that is about to be added.
    _assert_stored_keys_satisfy_the_check(connection)

    op.create_check_constraint(
        "scope_key_canonical",
        "policy_assignments",
        _CANONICAL_CHECK,
    )
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
