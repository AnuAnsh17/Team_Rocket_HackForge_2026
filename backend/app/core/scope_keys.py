"""The normalization contract for text-valued policy scope keys.

WHY THIS MODULE EXISTS
----------------------
A policy assignment is scoped by either a UUID (``scope_id``) or a text key
(``scope_key``). A text key is matched against a value the claim presents -- a
jurisdiction code, an expense category, a legal entity name -- so two keys that mean
the same thing must be treated as the same thing in *both* places that matter:

1. **Matching**, in ``app/policy/resolution.py``, which decides whether an assignment
   applies to a claim.
2. **Uniqueness**, in the database, which decides whether two assignments can coexist.

These two previously used different functions: the resolver used
``str.strip().casefold()`` while the unique index used
``lower(COALESCE(scope_key, ''))``. So ``"in-mh"`` and ``" in-mh "`` could both be
stored even though the resolver considered them the same key, and Unicode case folding
(Python) is not the same operation as lowercasing (PostgreSQL, locale-dependent).

THE CONTRACT
------------
The canonical form of a text scope key is::

    canonical = collapse_whitespace(raw).casefold()

where ``collapse_whitespace`` trims every character in ``SCOPE_KEY_WHITESPACE`` from
both ends and reduces any run of those characters in the middle to a single space.

* Only the characters in ``SCOPE_KEY_WHITESPACE`` count as whitespace, and that set is
  pinned to exactly Python's ``str.isspace()`` definition by a test that recomputes it.
  It is not "whatever ``str.split()`` happens to do", because the database has to be
  able to apply the same rule -- and PostgreSQL's default ``btrim`` trims only spaces,
  so a rule defined by ``str.split()`` would silently disagree with it for a
  non-breaking space.
* ``casefold()`` is used rather than ``lower()``. Case folding is the Unicode-defined
  operation for caseless comparison; ``lower()`` is a display transformation. They
  differ for real inputs: ``"ß".casefold() == "ss"`` while ``"ß".lower() == "ß"``.

The canonical form is **idempotent**: normalizing it again returns it unchanged. That
property is what lets a stored key be treated as already-normalized.

How consistency is guaranteed
-----------------------------
By construction, not by reimplementing Python in SQL:

* ``scope_key`` **stores the canonical form**. It is a matching key, not a display
  string. The value an administrator typed is not preserved here; the display name for
  a legal entity lives on ``organizations.legal_entity_name``, and a jurisdiction code
  or category is displayed as-is.
* The unique index is over that canonical column, so **database uniqueness is over
  exactly the string the resolver compares.**
* The database additionally CHECKs what PostgreSQL can verify exactly --
  non-blank, no surrounding whitespace, already lowercased -- as defence in depth
  against a write that bypasses the application.
* ``app/models/policy.py`` normalizes on assignment through a SQLAlchemy validator, so
  the ORM cannot store a non-canonical key.

Known residual, stated rather than hidden
------------------------------------------
PostgreSQL cannot compute ``casefold()``. A row inserted by a path that bypasses the
application *and* whose key PostgreSQL's ``lower()`` leaves unchanged, *and* which
Python's ``casefold()`` would alter, could still be stored non-canonically. Matching
canonicalizes both sides, so such a row still matches correctly rather than becoming
inert; the residue is that it could coexist with its canonical twin under the unique
index, which surfaces as a reported resolution *conflict* rather than a silent
duplicate. Closing that completely would mean either restricting keys to ASCII (which
would reject legitimate non-ASCII legal entity names) or maintaining a hand-written
replica of Unicode case folding in SQL, which is the mistake this module exists to
undo.

Deliberately not part of the contract
-------------------------------------
Unicode normalization (NFC/NFKC) is **not** applied. It is a separate decision with its
own consequences -- NFKC in particular folds compatibility characters such as
full-width forms and ligatures, which is a compatibility judgement about jurisdiction
codes and category labels, not a bug fix. Adding it silently would be exactly the kind
of undocumented semantic change that produced the original defect.
"""

from __future__ import annotations

import re

__all__ = [
    "MAX_CANONICAL_SCOPE_KEY_LENGTH",
    "SCOPE_KEY_WHITESPACE",
    "BlankScopeKeyError",
    "canonical_form_sql",
    "canonical_match_key",
    "is_canonical_scope_key",
    "normalize_scope_key",
]

# The whitespace characters that are trimmed and collapsed.
#
# Deliberately an explicit set rather than str.split(): the database must apply the same
# rule, and PostgreSQL's default btrim() trims only the space character. Deriving this
# from str.isspace() at import time would mean scanning the whole Unicode space, so the
# set is written out and a test asserts it equals
# {chr(c) for c in range(0x10000) if chr(c).isspace()} -- Python's whitespace is entirely
# within the BMP, so that check is complete. If the set ever changes, that test fails and
# the SQL in the migration has to be updated with a new migration, which is the point.
SCOPE_KEY_WHITESPACE = (
    "\t\n\x0b\x0c\r "
    "\x1c\x1d\x1e\x1f"
    "\x85\xa0"
    "\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)

# Longest canonical key the column accepts. VARCHAR(200) on the stored column; the same
# bound is asserted in Python so the failure is legible before it reaches the database.
MAX_CANONICAL_SCOPE_KEY_LENGTH = 200

_WHITESPACE_RUN = re.compile(f"[{re.escape(SCOPE_KEY_WHITESPACE)}]+")


class BlankScopeKeyError(ValueError):
    """Raised when a text scope key is empty or only whitespace.

    A key that normalizes to the empty string can never match anything, so storing one
    would create an assignment that looks configured and can never apply. That is the
    same class of defect as the scope-selector mismatch, and it is refused rather than
    stored.
    """


def _canonical(raw: str) -> str:
    """The canonical form of a raw key. See the module docstring for the definition."""
    return _WHITESPACE_RUN.sub(" ", raw.strip(SCOPE_KEY_WHITESPACE)).casefold()


def canonical_form_sql(column: str) -> str:
    """The canonical form of ``column``, expressed in SQL.

    Lets the database CHECK that a stored key equals its own canonical form, so a write
    that bypasses the application still cannot store a key the resolver would not
    recognize. Built from ``SCOPE_KEY_WHITESPACE`` so the whitespace rule has exactly one
    definition in code.

    A migration cannot import this: migrations are frozen, and importing live code would
    make an already-applied revision change meaning when behaviour changes. The migration
    that introduced this constraint therefore carries a verbatim copy, and a unit test
    asserts the two agree.

    ``lower()`` is PostgreSQL's operation, not Python's ``casefold()`` -- see the module
    docstring for the residue that leaves and why it is acceptable.
    """
    return (
        "lower("
        "regexp_replace("
        f"btrim({column}, '{SCOPE_KEY_WHITESPACE}'),"
        f" '[{SCOPE_KEY_WHITESPACE}]+',"
        " ' ',"
        " 'g'"
        ")"
        ")"
    )


def normalize_scope_key(raw: str | None) -> str | None:
    """Return the canonical form of a key to be **stored**.

    ``None`` passes through as ``None`` (an absent key). Blank or whitespace-only input
    raises :class:`BlankScopeKeyError` -- this is the write path, and a storeable key
    must be matchable.
    """
    if raw is None:
        return None
    canonical = _canonical(raw)
    if not canonical:
        raise BlankScopeKeyError(
            "a text scope key must contain at least one non-whitespace character: a key "
            "that normalizes to an empty string can never match a claim, so the assignment "
            "would look configured and never apply"
        )
    if len(canonical) > MAX_CANONICAL_SCOPE_KEY_LENGTH:
        raise ValueError(
            f"a text scope key may be at most {MAX_CANONICAL_SCOPE_KEY_LENGTH} characters "
            f"after normalization, but this one is {len(canonical)}. The stored column is "
            "that width, and a key that cannot be stored is not a key."
        )
    return canonical


def canonical_match_key(raw: str | None) -> str | None:
    """Return the canonical form of a key for **comparison**.

    Unlike :func:`normalize_scope_key`, blank input yields ``None`` instead of raising.
    This is the read path: a claim whose category is blank or missing simply has no
    value for that dimension, which means it matches no assignment -- it is not an
    error.
    """
    if raw is None:
        return None
    return _canonical(raw) or None


def is_canonical_scope_key(value: str | None) -> bool:
    """Whether ``value`` is already in canonical form.

    Non-raising, so it can be used inside validation error messages.
    """
    if value is None:
        return False
    return bool(value) and _canonical(value) == value
