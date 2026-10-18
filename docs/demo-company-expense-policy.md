# DEMO ONLY — FICTIONAL EXPENSE REIMBURSEMENT POLICY

> **This policy is fiction.** It exists so the Proofline demo organization has a
> coherent, company-shaped policy to evaluate against. It is **not** an employer
> policy, **not** legal, tax or accounting guidance, and **not** suitable for any
> real reimbursement decision. Every clause below is invented for a demonstration.
> The seeded policy version and every rule row carry the same label, and the
> registry refuses to execute any of them unless the explicit local demo flags are
> enabled (see *Activation* below).

Organization: the existing seeded demo organization (slug `demo-holdings`). No
second organization is created.

Currency: Indian Rupee (INR) only. See DEMO-EXP-014.

---

## Part A — Individual expense ceilings

Each clause states a **fictional per-claim ceiling**. A ceiling applies to one
claim; it is not a daily, monthly or per-night allowance. The amounts are
invented, are stored as rule parameters in the database rather than as literals in
code, and are evaluated with exact decimal arithmetic.

| Clause ID | Category | Fictional per-claim ceiling (INR) | Notes |
|---|---|---:|---|
| DEMO-EXP-001 | Meal | 1,500 | Applies to an individual meal claim. |
| DEMO-EXP-002 | Accommodation | 8,000 | **Per claim, explicitly not per night.** No room-night arithmetic is performed. |
| DEMO-EXP-003 | Ground transport | 2,500 | Taxi, ride-hailing and similar ground transport. |
| DEMO-EXP-004 | Fuel | 6,000 | Fuel and vehicle charging. |
| DEMO-EXP-005 | Office supplies | 10,000 | Stationery and general office purchases. |
| DEMO-EXP-006 | Air travel | 25,000 | A single air travel claim. |
| DEMO-EXP-007 | Rail / bus | 12,000 | Rail, metro and bus tickets. |
| DEMO-EXP-008 | Parking | 1,200 | Parking and local tolls. |
| DEMO-EXP-009 | Conference | 20,000 | Conference, event and equipment rental. |
| DEMO-EXP-010 | Telecom | 3,000 | Telecom, courier and business connectivity. |

**DEMO-EXP-011 — Categories without a ceiling.** A category that has no clause in
the table above is *not* automatically compliant. It is reported as **UNKNOWN**:
the policy says nothing about it, so the check cannot pass it. In particular the
`medical` and `other` categories carry no fictional ceiling, and a claim in either
category resolves to UNKNOWN rather than PASS.

**DEMO-EXP-012 — A ceiling is a flag for review, not a decision.** Exceeding a
fictional ceiling produces a FAIL finding that describes the expected ceiling, the
observed amount and the calculation. It does not reject, block, or approve
anything. No rule in this policy is permitted to transition a claim.

**DEMO-EXP-013 — Missing or unreliable amounts.** If a claim's amount is absent,
unreadable, or comes from unreviewed receipt extraction, the ceiling cannot be
applied and the result is UNKNOWN. UNKNOWN is never converted into PASS.

**DEMO-EXP-014 — Currency limitation.** The ceilings above are defined in INR and
are only evaluated when the claim's currency is INR. A claim in any other currency
resolves to UNKNOWN. No exchange rate, rate date or rate source is configured, so
no conversion is performed and none is implied. (Real multi-currency support would
require an approved rate source; see *Future extensions*.)

## Part B — Evidence and business context

**DEMO-EXP-015 — Receipt requirement.** An itemised receipt is expected for every
claim. A claim with no receipt attached is reported as UNKNOWN, not as a breach.

**DEMO-EXP-016 — Business purpose.** A claim should state a business purpose and,
where applicable, the client or attendee count. This clause is **not evaluated**:
which categories require which context is a policy decision that has not been
made, so the evaluator reports that it cannot answer (UNKNOWN) rather than
asserting that context is missing.

## Part C — Review and exceptions

**DEMO-EXP-017 — Human decision required.** Every finding produced under this
policy is advisory. A finance reviewer makes the reimbursement decision.

**DEMO-EXP-018 — Exception handling.** A reviewer may accept a claim above a
fictional ceiling where the business purpose supports it. This policy does not
model an exception workflow, so no automated exception path exists.

**DEMO-EXP-019 — Review escalation.** Claims whose policy result is UNKNOWN, or
which exceed a ceiling, are surfaced for human review. No approval hierarchy is
modelled; escalation routing is a future extension.

## Activation

The rules are seeded only when **all** of the following hold:

- `APP_ENV` is `development` or `test`
- `DEMO_MODE=true`
- `DEMO_SYNTHETIC_POLICY_ENABLED=true`

`DEMO_SYNTHETIC_POLICY_ENABLED` defaults to `false`, and configuration validation
refuses to start with it enabled outside a local environment. When the flag is
false the registry loads no fictional rule at all, so claims evaluate to UNKNOWN —
never to a fictional PASS.

## Future extensions (documented, deliberately NOT implemented)

These are named so the gap is explicit rather than silently absent. None of them
is evaluated by the current engine, and none of the data they would need is
invented here:

- **Aggregate ceilings** — daily, monthly or per-trip totals. Would need a
  resolved policy period and an approved aggregation window.
- **Grade-based thresholds** — different ceilings per job grade. Would need a
  verified mapping from grade to allowance, which the seeder deliberately leaves
  unset because it implies exactly such an assumption.
- **Per-night accommodation arithmetic** — would need room-night counts and a
  trusted night count on the claim.
- **Deadline rules** — submission windows. Would need an approved period policy.
- **Approval hierarchies** — routing by amount or grade. Would need an approved
  approval-matrix clause.
- **Foreign-currency conversion** — would need an approved rate source, rate date
  and rounding rule.
- **Medical and other categories** — no fictional ceiling is invented for them.

## Clause identifier convention

Clause IDs are stable strings of the form `DEMO-EXP-NNN` and are stored on each
rule row in `source_clause`, alongside a `source_excerpt` and the validating
actor. The policy version is `DEMO ONLY` and `FICTIONAL`. Nothing in this document
is an authoritative company clause.
