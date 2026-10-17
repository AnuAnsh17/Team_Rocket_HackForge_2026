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

## Safe defaults until resolved

- Never use illustrative limits from a draft/demo narrative as real policy values.
- Missing critical information returns UNKNOWN and follows an explicit review/correction path.
- Duplicate matching creates a candidate, not a confirmed duplicate.
- Ambiguous policy interpretation remains explicit and is routed for human review.
- Do not automatically reject a claim solely because of OCR uncertainty, model-generated risk or a duplicate similarity score.
- Every active rule needs tests and a verified source reference.
