# Contributing to Proofline

## Branching and pull requests

1. Start from the latest `origin/develop` and create a short-lived task branch, such as `feat/backend-receipt-ingestion`, `feat/mobile-receipt-capture`, or `feat/console-expense-review`.
2. Commit only task-related changes with descriptive messages.
3. Push the branch and open a pull request targeting `develop`.
4. Wait for the relevant CI checks to pass, request review from another teammate, resolve review comments, and merge after review.
5. Prefer squash merging for short-lived feature branches when the repository supports it.
6. Delete a merged feature branch when it is safe to do so.
7. Keep task branches short-lived and synchronize with `develop` regularly. Never rewrite shared branch history or force-push shared branches.
8. Use a release pull request from `develop` to `main` only after a milestone has been validated. Do not develop directly on `main`.

Use `feat/*`, `fix/*`, and `chore/*` prefixes for short-lived task branches. `main` is for stable, release-ready code; `develop` is the shared integration branch. The historical `chore/proofline-project-scaffold` branch is retained as the scaffold baseline.

## Ownership and shared contracts

`.github/CODEOWNERS` routes review requests by component. It does not by itself require approval. Request a reviewer from the relevant ownership area and another teammate for cross-cutting work.

The backend owns the canonical API schema, generated OpenAPI contract, and generated API client. Frontend teams must not independently change the canonical backend API schema or generated API client. Coordinate API changes with the backend owner and update the schema, generated client, documentation, and affected clients together. Root dependency manifests and lockfile changes affect every workspace and should be coordinated with the team.

Follow `AGENTS.md`, `PROOFLINE_BUILD_PLAN.md`, and the relevant documents under `docs/` before making cross-cutting changes. In particular, policy rules must be grounded in reviewed policy sources, and clients must not implement authoritative policy decisions.

## Pull request checklist

Use the repository pull request template to summarize the change, contract impact, validation, operational requirements, relevant security and privacy implications, and known limitations. Never commit credentials, private receipts, or real personal data.