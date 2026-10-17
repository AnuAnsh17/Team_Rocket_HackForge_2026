# Fixture Data

## The rule

**No real receipt, real employee name, real company, real email address or real
payment reference may enter this directory.** `data/samples/` is gitignored apart from a
`.gitkeep`, precisely so an actual receipt cannot be committed by accident.

If real, rights-cleared data is later authorized for use, it goes outside the repository
(e.g. a private bucket), and only a manifest referencing it is committed here.

## Contents

| Path | Purpose |
|---|---|
| `manifests/fixtures.example.json` | The required demo cases as a manifest: fixture id, category, what the input is, which fields are critical, expected duplicate relationships, expected state transitions. Expected *policy* results are deliberately `null`. |
| `samples/` | Empty. Placeholder for rights-cleared synthetic files when they exist. |

## Why the expected policy results are null

Each fixture needs a verified policy clause before an expected `PASS`/`FAIL`/`UNKNOWN`
can be written down. Until the authoritative policy document is available, filling those
in would be inventing policy - the exact thing `docs/policy-assumptions.md` forbids.

The manifest therefore records *what the case is* and *what must be true structurally*,
and leaves the policy outcome to be filled in by whoever validates the clause. A
fixture with `expected.policy_results: null` is complete as an input and incomplete as an
assertion, and that distinction is intentional.

## Fixture categories (from PROOFLINE_BUILD_PLAN.md section 10)

1. Clean receipt, all critical fields reliable.
2. Faded or rotated receipt with one uncertain critical field, routed to correction.
3. Required business-context field missing.
4. Arithmetic mismatch the receipt itself supports.
5. Individually acceptable claims whose aggregate exceeds a real limit - **only if the
   policy contains such a rule**.
6. The same transaction through two channels, one image altered: a candidate for review.
7. Hard negative: same amount and date, genuinely different transactions.
8. A clear policy exception.
9. A rule returning `UNKNOWN` because the necessary evidence or context is absent.
10. A correction that causes re-evaluation and preserves history.

Categories 5, 8 and 9 cannot be finalised without the policy document; they are listed
with their policy-dependent parts marked.

## A note on what the demo seed does

`backend/scripts/dev_seed.py` does **not** read this manifest. The seed creates
organizations and people only - no claims - because a claim must be created through the
application so that field provenance is written by the same code path a real claim uses.
These fixtures describe claims that will be created once that path exists.
