# Coding-Agent Instructions

This repository builds **Proofline**, an evidence-first expense auditor. These instructions apply to Hermes and every coding agent working here.

## Before changing code

1. Read PROOFLINE_BUILD_PLAN.md.
2. Read docs/api-contract.md before implementing frontend/backend integration.
3. Read docs/policy-assumptions.md before encoding or changing policy rules.
4. Read docs/architecture-decisions.md before making a structural decision that has
   already been made, and docs/authorization-matrix.md before touching access control.
5. Read docs/problem-statement-coverage.md before claiming that something works.
6. Inspect the current repository and existing implementation before editing.
7. Identify which modules and public contracts your change may affect.

## Source-of-truth rules

- FastAPI's generated OpenAPI schema is the machine-readable API source of truth. docs/api-contract.md is the human-reviewed contract. Keep them aligned.
- The backend alone makes authoritative policy and workflow decisions. Do not duplicate policy calculations in the Android app or dashboard.
- Policy decisions are deterministic code over reviewed and versioned rules, not free-form LLM judgments.
- Rule results are PASS, FAIL or UNKNOWN. Missing or ambiguous evidence cannot silently pass.
- A possible duplicate is a candidate, not proof of fraud. Never auto-reject a claim because of a similarity score.
- Never invent policy thresholds, city limits, time windows, exchange rates or eligibility rules. Use the actual policy and document ambiguities.
- Preserve receipt evidence and history. Corrections, re-extraction and review decisions must be traceable.
- Keep keys, service-role credentials, private receipts and personal data out of source control and client bundles.
- Demo shortcuts must be explicitly demo-only and disabled in production.

## Contract and collaboration rules

- Do not rename endpoints, fields, enums or response shapes unilaterally.
- If a contract change is necessary, update docs/api-contract.md, related tests and generated OpenAPI schema, then coordinate both clients.
- Use stable machine-readable codes and separate user-facing messages from internal IDs.
- Use decimal-safe money handling, ISO currency codes, ISO dates and UTC ISO timestamps.
- State-changing operations need authorization, validation, concurrency/idempotency behavior and an audit event.
- Do not expose public permanent object-storage URLs for receipts; use authorized streaming or short-lived signed access.
- Keep changes focused. Do not simultaneously rewrite files another agent owns.

## Required task protocol

For each substantial task:
1. State scope, files, contract impact, assumptions and acceptance criteria.
2. Implement the smallest coherent increment.
3. Add or update tests, fixtures and documentation.
4. Run relevant tests, lint/type checks and contract/schema checks.
5. Report changed files, exact commands/results, failures and remaining risks. Never claim a test passed if it was not run.

## Suggested task prompt

~~~text
Project: Proofline. Read AGENTS.md, PROOFLINE_BUILD_PLAN.md, docs/api-contract.md,
and docs/policy-assumptions.md before coding.

Task:
Scope/files:
Contract impact:
Assumptions / unresolved policy questions:
Acceptance criteria:
Tests to add and run:
Out of scope:

Report changed files, exact test commands/results, and remaining risks.
~~~
