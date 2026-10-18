# Proofline — live demo runbook

A three-minute walkthrough for judges, followed by optional deeper material. Every claim below is
grounded in the diagrams, which are grounded in the source at revision
`a779782f3fa093c31eb84aabdad11ee7e937ccb3`.

## Before you present (60 seconds of setup)

1. Open these five files in browser tabs, in this order:
   `proofline-system-architecture.html` → `proofline-expense-dataflow.html` →
   `proofline-expense-lifecycle.html` → `proofline-policy-audit-flow.html` →
   `proofline-auth-sequence.html`.
   Have `proofline-domain-erd.html` ready in a sixth tab for questions.
2. Pin the light theme once so every tab agrees. In any one tab's console:
   `localStorage.setItem('archify-theme','light'); location.reload();` — the preference persists
   across the others.
3. Leave motion on **Still** (the default) and enable **Live** only if you want the flow animation
   for step 1. Motion is reader-controlled; it is never required to explain anything.
4. Know the one thing you will *not* claim: nothing here proves OCR extracts text or that a payment
   happens. Both are addressed explicitly in the script where a judge is most likely to ask.

---

## The three-minute walkthrough

### Step 1 — The big picture (35s) · `proofline-system-architecture.html`

**Focus:** the client group at the left, then the `FastAPI API` node, then the `PostgreSQL` node.
**Trace:** the main path from a client through the API into the data stores — the emphasised edges.

> "This is Proofline. Three clients — an internal console for finance, an employee portal and an
> Android app — all talk to one FastAPI service. Every request is authenticated and then authorized
> by permission and organization scope before any domain work happens. Behind the API sit the
> expense and receipt domain services, a deterministic policy engine, and PostgreSQL."

**Key point:** one service, one contract, clear boundaries — and the authorisation boundary sits in
front of the domain, not inside it.

### Step 2 — Follow an expense (40s) · `proofline-expense-dataflow.html`

**Focus:** the draft-claim node, then the receipt upload, then the extraction-run node.
**Trace:** the emphasis path from client input to the stored receipt and its metadata.

> "An employee creates a draft claim, attaches a receipt, and the bytes go to private object storage
> while the metadata lands in its own table. Extraction is queued as a *run* — and here is the honest
> part: the extraction provider defaults to unavailable and the other providers fail closed, so the
> diagram shows a pending run rather than pretending text came out. The important structural fact is
> that raw content and metadata are separate, and every field keeps its provenance."

**Key point:** the data model distinguishes receipt bytes, receipt metadata, extracted fields and
user-corrected fields — that separation is what makes an audit defensible.

### Step 3 — Explain the decision layer (45s) · `proofline-policy-audit-flow.html`

**Focus:** the `Policy pre-flight` node, then the evaluator, then the `Audit service` node.
**Trace:** the advisory path first, then the persisted-decision path.

> "Policy evaluation is deterministic: a registry of rules, an evaluator, and a resolver that picks
> the governing policy version. It returns one of three answers — PASS, FAIL, or UNKNOWN. UNKNOWN is
> a real answer: it means the evidence or the policy context is insufficient, and it routes to a
> human rather than silently passing. The advisory pre-flight returns that result and writes
> nothing at all — I verified it contains zero session writes. When a human decides, that decision
> and its audit event are appended in one transaction."

**Key point:** the engine advises, a human decides, and the two paths are visually distinct.

### Step 4 — Demonstrate accountability (35s) · `proofline-policy-audit-flow.html` (or D)

**Focus:** the `audit_events` node and the append-only boundary.
**Trace:** the write path into the audit store.

> "Every state-changing action leaves an audit event. That table is append-only — enforcing it is a
> database trigger that refuses UPDATE and DELETE. I want to be precise about what that guarantees:
> it protects the record's integrity inside the database. It is not cryptographic immutability, not
> WORM storage, and not a legal claim. What it does mean is that the history you are looking at was
> not quietly rewritten."

**Key point:** we know exactly what our audit guarantee is, and we say so rather than overclaiming.

### Step 5 — Prove a real request (25s) · `proofline-auth-sequence.html`

**Focus:** the `console` participant, then `jwks`, then the `api` participant.
**Trace:** the message sequence from token to response, including the 401/403 branches.

> "This is one real protected request. The console attaches a Supabase access token; the API verifies
> it against the project's cached JWKS with an explicit issuer, audience and algorithm allow-list;
> the identity is resolved to a user and an active membership; permissions and organization scope
> are enforced; the service runs and the response comes back. The failure paths are on the diagram
> too - missing token is 401, insufficient permission or wrong organization is 403 or 404.
> One honest detail: only the console sends a token today. The portal and the Android app are wired
> with no token provider yet, so they exercise the demo identity path."

**Key point:** authorization is enforced server-side and fails closed — the client is never trusted
to tell us who it is.

---

## Closing line (10s)

> "So: evidence first, decisions recorded, and nothing claimed that the code does not do."

---

## Optional deeper material

**The data model — `proofline-domain-erd.html`.** 28 tables across identity, org structure, policy,
expense, receipts, review and audit. Two things worth showing: `audit_events` deliberately has **no
foreign keys** — an append-only table must not take part in cascading deletes — and money columns
are exact numerics, never floats. Use the table groups to answer "where does X live?" questions.

**The lifecycle — `proofline-expense-lifecycle.html`.** Show that `draft → submitted → approved` is
the main path, that `needs_info` is a real round trip back to the employee, and that `withdrawn` is
reserved and produced by no endpoint. Be explicit that four different things are being kept apart:
submitting a claim, a policy check returning PASS, a reviewer approving, and paying — the last of
which does not exist in this codebase.

**If asked "is OCR working?"** Answer honestly: the plumbing around extraction is implemented —
uploads are validated, runs are persisted, results are schema-validated — but no provider is
enabled by default and none is benchmarked here, so no accuracy claim is made. There is a separate
receipt benchmark dataset for exactly that evaluation.

**If asked "what is not finished?"** Say it plainly: finding persistence from the engine's own
evaluation has no live caller yet, no payment execution exists, and the demo policy is fictional and
demo-gated. The diagrams mark these with dashed edges and cards rather than hiding them.

---

## Honesty checklist before you answer anything

- Do not say the system extracts text from receipts.
- Do not say a claim is paid.
- Do not say the audit log is tamper-proof or cryptographically immutable — say append-only by
  database trigger.
- Do not say duplicate candidates are fraud detections.
- Do not present the fictional demo policy as a real company policy.
- Do not claim the analytics dashboard is a work queue.
