# Team_Rocket_HackForge_2026

## Project: Proofline

**Proofline is an evidence-first expense auditor** for the Receipt Graveyard problem statement.

### Read this first

1. [Coding-agent instructions](./AGENTS.md) — mandatory context and collaboration rules for Hermes and other agents.
2. [Full product and build plan](./PROOFLINE_BUILD_PLAN.md) — product thesis, architecture, tech stack, data model, policy engine, security, testing, demo and rollout plan.
3. [Canonical API contract](./docs/api-contract.md) — endpoint names, DTOs, enums, state transitions, errors, idempotency and cross-client requirements.
4. [Policy assumptions and open questions](./docs/policy-assumptions.md) — do not invent policy thresholds; record source-backed rules and unresolved ambiguity here.

### Architecture rule

One backend, one canonical contract, one deterministic policy engine and one audit history. The Android app and finance dashboard are clients of the same API; neither client implements authoritative policy logic.

Before changing API shape or policy logic, read the linked docs and coordinate the change with the team.
