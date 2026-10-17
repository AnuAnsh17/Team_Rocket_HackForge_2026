# Problem Statement and Requirement Sources

This file is the **single source of truth for the requirement wording** that
`docs/problem-statement-coverage.md` traces against. Every requirement label used in that
report resolves to a quoted source here.

## 0. Provenance: what is quoted, and what is missing

Be clear about three different things, because they are not the same document.

| Source | Status | Quoted in |
|---|---|---|
| **A.** The original "Receipt Graveyard" hackathon problem statement | **NOT AVAILABLE.** It is not in this repository, it was never supplied in the working session, and it is not publicly retrievable (searches for the statement and the hackathon problem set returned nothing). | Section 2 - marked as an empty slot |
| **B.** The project's own problem statement, as recorded in `PROOFLINE_BUILD_PLAN.md` section 0 | Available in the repository | Section 1 |
| **C.** The authoritative scoping decision that expanded the product and listed the required coverage areas | Available; reproduced here so traceability does not depend on a file outside the repository | Section 3 |

**Source A has not been invented, paraphrased or reconstructed.** An earlier assessment
report (`docs/problem-statement-coverage.md`) already asked for it and will keep asking until
it is supplied. Nothing in this project should be described as having preserved the original
wording, because it has not.

To complete this file, paste the original statement below the marker in section 2. The
coverage matrix already traces to source labels, so no restructuring is needed when it
arrives - only the labels gain a new parent.

---

## 1. Source B - the project's problem statement, verbatim

From `PROOFLINE_BUILD_PLAN.md`, section 0:

> **Problem:** The Receipt Graveyard — turn messy receipts and a layered expense policy into
> accurate, explainable, reviewable reimbursement decisions, including duplicates and
> month-wide patterns.

This is the project's own one-line restatement. It is **derived** wording, not the original
statement, and it is labelled as such wherever it appears in the repository.

---

## 2. Source A - the original problem statement, verbatim

### NOT SUPPLIED

The verbatim text of the original Receipt Graveyard problem statement has not been provided.
It is deliberately left empty rather than filled with a plausible-sounding reconstruction,
because a reconstructed statement would silently redefine what the project is judged against,
and every "coverage" claim built on it would then be measured against the wrong target.

**Action required:** paste the original statement here.

```
<!-- PASTE THE ORIGINAL PROBLEM STATEMENT VERBATIM BELOW THIS LINE -->

```

### Why this matters more than it looks

`docs/problem-statement-coverage.md` evaluates how much of the problem the design and the
scaffold address. Without source A it evaluates against source C, which is a derived
requirements list. Source C is a faithful record of what this project was asked to build, but
it is not independent evidence that the requirement list is complete. If the original
statement contains a requirement that source C omits, this report would not notice its
absence - and that is the specific failure mode the empty slot above exists to prevent.

---

## 3. Source C - expanded scope and required coverage areas, verbatim

Reproduced verbatim from the approved scoping decision that authorised the scaffolding phase.
It is the requirement source the coverage report's matrix traces against.

### 3.1 The scope boundary for the scaffolding phase

> **Important scope boundary:** Create the folders, documentation, configuration, dependency
> manifests, database/migration foundations, typed interface/schema placeholders and minimal
> application bootstrap shells. Do not implement the actual expense-auditing features yet. The
> only code permitted in this phase is minimal scaffolding required for the applications and
> development tools to initialize and validate. No production feature logic.

### 3.2 The three client experiences

> We are building three client experiences backed by one shared backend.

- **Employee Android app** — React Native + Expo + TypeScript: employee home; receipt
  capture/gallery upload; extracted-field review; expense submission; my expenses and
  reimbursement status; correction requests and claim details. "The mobile app must use the
  same employee permissions and API contracts as the employee web portal. It must not
  implement policy rules or trust client-supplied user IDs to establish ownership."
- **Employee web portal/dashboard** — Next.js + TypeScript + Tailwind: employee overview;
  upload and submit; review and correct extracted information; add required business purpose,
  trip, client and attendee context when applicable; my expenses, status timeline and
  correction requests; personal spending/allowance overview based on the employee's authorized
  policy profile; plain-language explanations of findings and required information. "An
  employee must only be able to access their own claims, receipts, status, personal allowance
  profile and associated history, except for explicitly authorized delegated access."
- **Internal HR / Finance / Admin console** — Next.js + TypeScript + Tailwind: "Use **one
  internal console with role-specific navigation, pages and actions** rather than building
  separate, duplicated applications for HR, finance, and administrators." Sections: HR review,
  manager approval, finance review, finance administration, organization administration,
  policy administration.

> Do not assume every organization must have all these approval stages enabled. The workflow
> should eventually support configurable approval requirements, with the actual workflow and
> rules determined by the approved company policy.

> Do not give HR, managers, finance or organization administrators universal permissions just
> because they have a privileged-looking role name. Each role must have explicit, documented
> permissions.

### 3.3 The twelve authentication and authorization requirements

> 1. Identity verification through validated authentication tokens.
> 2. Server-side JWT signature, issuer, audience and expiration validation using the selected
>    provider's supported mechanism.
> 3. Server-controlled user membership and authorization records; the client cannot grant
>    itself roles or privileges.
> 4. Organization/tenant scoping for all organization-owned records.
> 5. Resource-level access checks on expenses, receipts, findings, history, policy
>    information, uploads and mutations.
> 6. A user cannot access another employee's data simply by changing a URL, UUID, request
>    parameter, or API payload.
> 7. Employee access is restricted to their own claims and permitted profile fields.
> 8. Managers can access direct reports only through explicitly authorized relationships and
>    permissions.
> 9. HR and finance access is scoped to the claims, fields, departments or review queues they
>    are authorized to handle.
> 10. Organization and policy administrators receive only the administrative capabilities
>     assigned to them.
> 11. Sensitive actions are audited with actor, target, action, timestamp, reason where
>     applicable, and request/correlation ID.
> 12. Role changes, employee deactivation, token revocation/expiry and loss of organizational
>     membership must be considered in the security design.

> Do not trust a client-provided role, employee ID, department ID, grade, allowance or approval
> limit. Derive the authenticated actor from validated identity, then retrieve the actor's
> authoritative membership, permissions and applicable profile server-side.

> A demo identity switcher may be supported exclusively in explicitly enabled, non-production
> demo mode. It must be impossible to use the demo mechanism to gain another user's identity
> or administrative permissions in production. Fail closed when demo authentication is
> disabled.

### 3.4 Policy resolution dimensions

> 1. Organization or legal-entity baseline.
> 2. Jurisdiction, office or location-specific policy.
> 3. Employee grade/job level.
> 4. Department or cost center.
> 5. Business trip or expense-specific context.
> 6. An explicit, authorized and time-bounded exception.

> These are supported dimensions for the architecture, not a claim that every organization uses
> this exact hierarchy.

> **Do not silently assume that a higher job level always means a higher allowance or that the
> most specific policy always overrides every other rule.** The approved policy determines the
> semantics. The design must make effective assignments, rule precedence, effective dates and
> exceptions explicit and deterministic.

> If applicable rules conflict or required context is absent, the resolver must report an
> explicit unresolved/unknown outcome for review instead of inventing a decision.

### 3.5 The sixteen required coverage areas

This is the list `docs/problem-statement-coverage.md` traces. Requirements **R1** to **R16**
in that report are these bullets, in this order, one for one.

> - Messy, faded, rotated, cropped, handwritten and incomplete receipt processing.
> - Correct extraction of merchant, dates, totals, currency and itemization.
> - Layered expense policies and interacting rule conditions.
> - Employee-specific allowances, hierarchy and approval requirements.
> - Required business context such as client names and attendee counts.
> - Category caps and daily/cumulative limits where present in the actual policy.
> - Non-reimbursable items and partial eligibility where policy permits.
> - Arithmetic inconsistencies.
> - Exact and image-variant duplicates, including cross-channel candidates.
> - Suspicious patterns that warrant review without unsupported fraud claims.
> - Month-long accumulation and re-evaluation as claims arrive or change.
> - Multi-employee account security and role-based access.
> - Employee corrections and reviewer workflows.
> - Explainable findings, policy provenance and audit history.
> - Currency normalization where required.
> - Human review and accountable reimbursement decisions.

### 3.6 How the statuses must be assigned

> 4. Status at the end of scaffolding: `DOCUMENTED`, `SCAFFOLDED`, `IMPLEMENTED`, `TESTED`, or
>    `NOT ADDRESSED`.

> Do not count folder creation or interface placeholders as implemented problem-solving
> capability.

> If you provide percentages, explain the denominator and methodology. Clearly distinguish a
> subjective design-coverage estimate from verified functional completion or benchmark accuracy.
> Do not claim that the scaffold solves the whole problem.

### 3.7 What must not be built in the scaffolding phase

> Do not implement the full product, connect a live OCR provider, create actual reimbursement
> rules, simulate successful authentication without validation, or claim that any feature is
> production-ready during this phase.

> During scaffolding, establish the entities, relationships, interfaces, documentation and
> migration foundations only. Do not invent actual grade levels, employee allowances, policy
> caps, approval thresholds or organizational rules.

---

## 4. What is still outstanding

| Item | Status |
|---|---|
| Source A: the original problem statement, verbatim | **Not supplied.** Section 2 is an empty slot. |
| The authoritative company policy document (clauses, caps, thresholds, approval stages) | Not supplied. Blocks 8 of the 16 requirement areas. |
| The receipt dataset and its authorized use | Not supplied. Blocks extraction and every extraction metric. |
| A chosen extraction provider and its credentials | Not chosen. |
| A labelled duplicate positive/negative set | Not supplied. |
| The organization's grade structure and allowance data | Not supplied. |

Reconciling the coverage matrix against source A once it arrives remains an open action, and
it is listed as such in `docs/problem-statement-coverage.md` section 7.
