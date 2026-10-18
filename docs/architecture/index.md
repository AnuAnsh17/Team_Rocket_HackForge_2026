# Proofline — From Expense to Evidence

**Proofline turns a pile of employee expense receipts into evidence a reviewer can actually
defend: every claim, every extracted field, every policy outcome and every human decision
keeps its own provenance and lands in an append-only audit trail.**

This folder is a collection of six interactive architecture diagrams of the real system. They are
generated from the source, not drawn from memory: every diagram cites the files and lines it
describes.

---

## Start here

| # | View | What it answers | Open it |
|---|---|---|---|
| A | **System architecture** *(primary showcase)* | What is Proofline made of, and where does a request go? | [HTML](proofline-system-architecture.html) · [JSON source](proofline-system-architecture.json) |
| B | **Expense & receipt data flow** | What happens to a receipt from upload to review? | [HTML](proofline-expense-dataflow.html) · [JSON source](proofline-expense-dataflow.json) |
| C | **Expense claim lifecycle** | Which states exist, what moves a claim, and what does not | [HTML](proofline-expense-lifecycle.html) · [JSON source](proofline-expense-lifecycle.json) |
| D | **Authentication & authorization** | How one protected request is authenticated and scoped | [HTML](proofline-auth-sequence.html) · [JSON source](proofline-auth-sequence.json) |
| E | **Domain data model** | The real tables, columns, keys and constraints | [HTML](proofline-domain-erd.html) · [JSON source](proofline-domain-erd.json) |
| F | **Policy evaluation & audit traceability** | How a policy result is produced, and what the audit record really guarantees | [HTML](proofline-policy-audit-flow.html) · [JSON source](proofline-policy-audit-flow.json) |

## Recommended presentation order

**A → B → C → F → D**, with **E** as the technical appendix.

A sets the stage, B follows the data, C shows the states it passes through, F explains the
decision-making layer and the accountability it leaves behind, D proves a real request is
authenticated and scoped. E is the deepest view and works best for engineering questions rather
than the opening narrative. The full narrative, with what to say at each step, is in
[demo-runbook.md](demo-runbook.md).

---

## What Proofline is, in one screen

Three clients (**internal console**, **employee portal**, **Android app**) talk to one **FastAPI**
service over `/api/v1`. Eight routers are registered — health, meta, identity, expense lifecycle,
analytics, expenses, receipts, policy — plus a demo router that only exists when demo mode is on.

Requests are authenticated by a pluggable provider and then **authorized by permission and
organization scope** before any domain work happens. Claims move through an explicit workflow with
optimistic concurrency and idempotency keys. Receipts are stored privately and served only through
an authorization-checked endpoint. A deterministic policy engine evaluates a claim and returns
**PASS, FAIL or UNKNOWN**; the advisory pre-flight returns that result and writes nothing.
PostgreSQL holds 28 application tables across four migrations (29 relations counting Alembic's own version table), and `audit_events` is append-only.

## Implementation status legend

Every diagram uses the same semantics. Treat these as the honest status of the code, not a roadmap
promise:

| Status | Meaning | How it is drawn |
|---|---|---|
| **Implemented** | Reachable in current source, route registered, service executes, tests cover it | Solid edge, solid boundary |
| **Partial** | Real code exists, but the full intended behaviour is not wired or not verified end to end | Solid node, dashed edge, stated in a card |
| **Planned / not verified** | No code path establishes it | Dashed, or absent entirely |

Concrete status of the things most often over-claimed:

- **Receipt text extraction is not proven working.** `EXTRACTION_PROVIDER` defaults to
  `unavailable` and the non-default providers fail closed. Uploads persist an extraction *run*;
  that is not evidence that text was extracted. The diagrams model a pending or unavailable run.
- **The policy pre-flight writes nothing.** It is advisory. Verified: `policy_check_service.py`
  contains zero `session.add` / `session.commit` calls. It creates no finding, no status change and
  no audit event.
- **A reviewer approving a claim is not payment.** No payment or reimbursement execution exists
  anywhere in the codebase.
- **The audit trail is append-only by database trigger** (`trg_audit_events_append_only`, migration
  `0001`). That is a real integrity guarantee and it is *not* cryptographic immutability, not WORM
  storage, and not a legal-admissibility claim. The evidence model in Diagram F says exactly this.
- **Duplicate candidates are signals, not fraud determinations.** A reviewer confirms or dismisses.
- **The demo expense policy is fictional** (`../demo-company-expense-policy.md`) and is seeded only
  under local demo flags. It is not an authoritative company policy.
- **Analytics are read-only projections** over persisted claims. They are not a work queue.

---

## Reading these diagrams

- **Light by default is environment-dependent.** The Archify runtime resolves the initial theme from
  `localStorage['archify-theme']`, falling back to the operating system's `prefers-color-scheme`.
  The schema has no authored theme field, so the artifact cannot force light on its own. To pin it
  for a demo, set the preference once in the browser console on any one diagram and it persists for
  all of them:

  ```js
  localStorage.setItem('archify-theme', 'light'); location.reload();
  ```

  The theme toggle in the viewer always works, so this is convenience rather than a requirement.
  Validation covers light at four viewports (1440×900, 1600×1000, 1920×1080, 2048×1320) and dark at
  both endpoints.
- **Interaction.** Click or focus a node for its details and its authored upstream/downstream facts.
  Node Finder searches labels and stable ids. Route Probe resolves a path between two chosen
  endpoints over authored relationships. Reading Depth starts at READ and reveals more detail as you
  zoom. The viewer's own Guide button (or `?`) lists every action and shortcut.
- **Motion.** Each diagram enables reader-controlled Live/Still motion; it starts Still and the
  Live/Still control is in the viewer. Reduced-motion, print and export all preserve full static
  meaning.
- **Deep links.** Each diagram declares guided views in its JSON, but the generated artifact does
  not expose them as navigable ids, so treat them as authored intent rather than clickable entry
  points. `demo-runbook.md` therefore gives manual focus instructions instead of URLs — no
  unverified link format is presented here.

## Evidence basis

All six diagrams are pinned to the same revision:

| | |
|---|---|
| Repository | `https://github.com/AnuAnsh17/Team_Rocket_HackForge_2026` |
| Revision | `a779782f3fa093c31eb84aabdad11ee7e937ccb3` |
| Branch | `backend` |
| Working tree | clean at that revision when the diagrams were generated |

Individual nodes carry their own `sources` references (path plus line range where verified) and the
viewer surfaces them on focus. Where a line range could not be confirmed, the citation names the
path without a line rather than presenting an unverified range as proof.

Two disclosed limits, both stated inside the diagrams as well:

- **The ERD is authored at `standard` quality, not `showcase`.** Above roughly 8 tables the renderer's
  own guidance is to keep complete field visibility rather than promote every crossing to an error;
  the artifact still passes its browser check with the smallest projected text at 7.43px (floor 6px).
- **The ERD draws 57 of the schema's 79 foreign keys.** Not drawn: the four self-referencing foreign
  keys (which the renderer refuses as self-loops) and sixteen attribution keys to `users.id` (which
  would exceed one side's marker capacity). Every one of those columns still carries its key role and
  reference target in the table, so nothing is hidden at column level - the omissions are edge
  rendering only. `audit_events` genuinely has no foreign key at all, by design.

## Regenerating and validating

The editable JSON is the source of truth; the HTML is generated. To rebuild one diagram:

```bash
node "<archify-skill>/bin/archify.mjs" finalize \
  architecture docs/architecture/proofline-system-architecture.json \
  docs/architecture/proofline-system-architecture.html \
  --repo-root . --quality showcase --json
```

`finalize` runs the full chain — schema validation, delivery, strict check, and a real-browser
check. A non-zero exit is not success; read the receipt and repair the candidate.
