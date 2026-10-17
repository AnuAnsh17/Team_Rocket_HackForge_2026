# Policy Assumptions and Questions

This document prevents agents from silently inventing reimbursement rules. Update it after inspecting the actual company policy and receipt dataset.

## Current status

- Authoritative policy source: not yet recorded in this repository.
- Policy version/effective date: pending review of the supplied policy.
- Receipt dataset and permission to use it: pending confirmation.
- Rule registry: do not activate invented numeric thresholds. Until source clauses are verified, implement neutral contract/scaffolding and clearly labelled synthetic fixtures only.

## Per-rule record required

| Field | Required information |
|---|---|
| Rule ID | Stable identifier |
| Source | Document name/hash, page/section/clause and exact relevant excerpt |
| Effective period | Start/end date if applicable |
| Applicability | Category, trip/office, city, currency, role or other preconditions |
| Inputs | Required fields/context and provenance |
| Logic | Deterministic condition, boundary and rounding semantics |
| Aggregate basis | Which claims are counted and which workflow states are included |
| Unknown behavior | Route when evidence/context is missing |
| Action | Informational, employee correction, reviewer review or other approved action |
| Tests | PASS, FAIL, UNKNOWN, boundary and exception tests |
| Approval | Who validated the interpretation |

## Questions to resolve from the actual policy

- Is a meal rule an individual cap, a cumulative daily limit, both, or neither?
- If a limit is exceeded, is only the excess ineligible, is the full expense ineligible, or is review required?
- Do aggregates include submitted, approved or reimbursed expenses? How are rejected claims, refunds and credits handled?
- What timezone defines the day boundary?
- Which location is authoritative for each rule?
- How are office expenses distinguished from business-trip expenses?
- Which categories require client names, attendee counts, itemization or other context?
- What approval thresholds and overrides actually exist?
- What currencies and conversion source/date/rounding rules apply?
- Is there a submission deadline?
- How are alcohol, tips, taxes, service charges, discounts and mixed eligible/ineligible items treated?
- May an external AI provider process the supplied receipt data, and under what retention/data-use terms?
- Are the receipt fixtures synthetic, public, or otherwise authorized for use?

## Findings from the scaffolding phase (2026-10-17)

The scaffolding established the following. None of it resolves a policy question; it
records where each question now physically blocks progress.

- **No policy document was supplied.** The policy registry therefore ships empty and the
  resolver returns unresolved. Every claim would evaluate to `UNKNOWN`. This is the
  correct behaviour, not a defect.
- **No grade levels, allowance profiles or allowance limits were created**, in the seed
  or anywhere else. An allowance item carrying an amount without a cited source clause
  and a currency is now **rejected by the database**
  (`ck_allowance_profile_items_limit_requires_source`), and a rule cannot be activated
  without a verified clause plus a recorded human validator
  (`ck_policy_rules_source_requires_validation`). An invented threshold is not merely
  discouraged; it cannot be stored.
- **`organizations.timezone` is nullable**, because the operating timezone is unresolved.
  Any period-based rule will report an unresolved reason and therefore `UNKNOWN` rather
  than assuming a day boundary.
- **`organizations.reporting_currency` is nullable**, and `expenses.amount_reporting` is
  always null: no exchange rate is applied.
- **No approval stage was invented.** `approval_tasks` models a stage and records
  `requirement_basis`, but nothing decides that a stage is required.
- **Duplicate scoring is a ranking signal only.** Perceptual similarity is not
  implemented and reports no score rather than a fabricated one.

## Open questions carried forward

Added during scaffolding, beyond those listed above:

- Does the policy define caps per **category**, per **period**, per **employee grade**, or
  some combination? The dimension model supports all four, but only the policy can say
  which apply.
- When two approved assignments apply at the same priority, what wins? Today the resolver
  reports a conflict and refuses to guess. A precedence rule must come from policy.
- What is the tolerance for **date proximity** in duplicate detection? Two receipts with
  the same amount three days apart - the same trip's meals, or a double claim? The current
  constant is zero days, which is a conservative placeholder, not a decision.
- Which workflow stages may an employee escalate past, and who holds override authority?
- What is the retention period for receipts and audit events, and does the audit trail
  need to be exported off-site?

## Safe defaults until resolved

- Never use illustrative limits from a draft/demo narrative as real policy values.
- Missing critical information returns UNKNOWN and follows an explicit review/correction path.
- Duplicate matching creates a candidate, not a confirmed duplicate.
- Ambiguous policy interpretation remains explicit and is routed for human review.
- Do not automatically reject a claim solely because of OCR uncertainty, model-generated risk or a duplicate similarity score.
- Every active rule needs tests and a verified source reference.
