"use client";

import { useEffect, useState } from "react";

import { Card, PageHeader } from "@/components/ui";
import { ApiError, unwrap, type components } from "@proofline/api-client";
import { API_BASE_URL, createConsoleApi, readDemoActorId } from "@/lib/api";

type Receipt = components["schemas"]["ReceiptResponse"];
type ExpenseSummary = components["schemas"]["ExpenseSummary"];
type Expense = components["schemas"]["ExpenseResponse"];
const api = createConsoleApi();

export default function ReviewQueuePage() {
  const [expenseId, setExpenseId] = useState("");
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [claims, setClaims] = useState<ExpenseSummary[]>([]);
  const [expense, setExpense] = useState<Expense | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionAction, setDecisionAction] = useState<"approve" | "reject" | "request_correction" | "escalate">("approve");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const hasActiveRuns = receipts.some((receipt) => ["pending", "running"].includes(receipt.extraction_status));

  useEffect(() => {
    void unwrap(api.GET("/api/v1/expenses", { params: { query: { limit: 50 } } }))
      .then((page) => setClaims(page.items))
      .catch((cause: unknown) => setError(cause instanceof ApiError ? cause.message : "The authorized review queue could not load."));
  }, []);

  useEffect(() => {
    if (!expenseId || !hasActiveRuns) return;
    const timer = window.setInterval(() => {
      void unwrap(api.GET("/api/v1/expenses/{expense_id}/receipts", {
        params: { path: { expense_id: expenseId } },
      })).then(setReceipts).catch((cause: unknown) => {
        setError(cause instanceof ApiError ? cause.message : "Receipt status could not refresh.");
      });
    }, 2500);
    return () => window.clearInterval(timer);
  }, [expenseId, hasActiveRuns]);

  async function loadReceipts(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const id = expenseId.trim();
      const [detail, receiptRows] = await Promise.all([
        unwrap(api.GET("/api/v1/expenses/{expense_id}", { params: { path: { expense_id: id } } })),
        unwrap(api.GET("/api/v1/expenses/{expense_id}/receipts", {
          params: { path: { expense_id: id } },
        })),
      ]);
      setExpense(detail);
      setReceipts(receiptRows);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not load the authorized claim and receipt records.");
      setReceipts([]);
      setExpense(null);
    } finally {
      setLoading(false);
    }
  }

  async function recordDecision(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!expense) return;
    setError(null);
    setLoading(true);
    try {
      await unwrap(api.POST("/api/v1/expenses/{expense_id}/decisions", {
        params: { path: { expense_id: expense.id }, header: { "Idempotency-Key": crypto.randomUUID() } },
        body: {
          action: decisionAction,
          expected_version: expense.version,
          reason: decisionReason || undefined,
        },
      }));
      setDecisionReason("");
      await loadReceiptsFor(expense.id);
      const page = await unwrap(api.GET("/api/v1/expenses", { params: { query: { limit: 50 } } }));
      setClaims(page.items);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "The review decision could not be recorded.");
    } finally { setLoading(false); }
  }

  async function loadReceiptsFor(id: string) {
    const [detail, receiptRows] = await Promise.all([
      unwrap(api.GET("/api/v1/expenses/{expense_id}", { params: { path: { expense_id: id } } })),
      unwrap(api.GET("/api/v1/expenses/{expense_id}/receipts", {
        params: { path: { expense_id: id } },
      })),
    ]);
    setExpense(detail);
    setReceipts(receiptRows);
  }

  async function openReceipt(contentUrl: string) {
    setError(null);
    const tab = window.open("about:blank", "_blank");
    if (!tab) {
      setError("Allow pop-ups to open the authorized receipt image.");
      return;
    }
    tab.opener = null;
    try {
      const headers = new Headers();
      const actorId = readDemoActorId();
      if (actorId) headers.set("X-Demo-Actor-Id", actorId);
      const origin = API_BASE_URL.replace(/\/api\/v1\/?$/, "");
      const response = await fetch(`${origin}${contentUrl}`, { headers, cache: "no-store" });
      if (!response.ok) throw new Error("The API refused receipt content access.");
      const objectUrl = URL.createObjectURL(await response.blob());
      tab.location.href = objectUrl;
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (cause) {
      tab.close();
      setError(cause instanceof Error ? cause.message : "Receipt content could not be opened.");
    }
  }

  return (
    <>
      <PageHeader title="Receipt extraction review" description="Inspect backend extraction and its validation signals against the authorized original receipt." />
      <Card title="Authorized claims" description="The backend limits this list to the selected actor's organization or direct reports.">
        {claims.length ? <ul className="space-y-2 text-sm">{claims.map((claim) => <li key={claim.id}><button className="underline" onClick={() => { setExpenseId(claim.id); void loadReceiptsFor(claim.id); }}>{claim.merchant ?? "Expense"} · {claim.status.replaceAll("_", " ")} · {claim.id}</button></li>)}</ul> : <p className="text-sm">No claims are visible to this actor.</p>}
      </Card>
      <Card title="Load an expense" description="Enter an expense ID. The backend enforces organization and relationship scope for metadata and content.">
        <form onSubmit={(event) => void loadReceipts(event)} className="flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="expense-id">Expense ID</label>
          <input id="expense-id" value={expenseId} onChange={(event) => setExpenseId(event.target.value)} required className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] px-3 py-2" placeholder="Expense UUID" />
          <button disabled={loading} className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-white disabled:opacity-50">{loading ? "Loading…" : "Load receipts"}</button>
        </form>
        {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      </Card>
      {receipts.map((receipt) => {
        const run = receipt.extraction_runs?.at(-1);
        const fields = run?.structured_result;
        return <Card key={receipt.id} title={`Receipt ${receipt.id}`} description={`Status: ${receipt.extraction_status} · ${run?.provider ?? "no extraction run"}${run?.model ? ` / ${run.model}` : ""}`}>
          <button type="button" className="mb-4 underline" onClick={() => void openReceipt(receipt.content_url)}>Open authorized original</button>
          {run?.error_code && <p className="mb-3 text-sm text-amber-800">Extraction code: {run.error_code}</p>}
          {fields ? <dl className="grid gap-3 text-sm sm:grid-cols-2">{(["merchant", "transaction_date", "currency", "subtotal", "tax_total", "tip", "discount", "grand_total", "receipt_number"] as const).map((key) => {
            const field = fields[key];
            if (typeof field !== "object" || field === null || !("status" in field)) return null;
            return <div key={key}><dt className="font-medium">{key.replaceAll("_", " ")}</dt><dd>{field.value ?? "No value"} · {field.status}</dd></div>;
          })}</dl> : <p className="text-sm">No structured result is available yet.</p>}
          {run?.structured_result?.line_items?.length ? <div className="mt-4"><p className="font-medium">Visible line items</p><ul className="mt-2 space-y-1 text-sm">{run.structured_result.line_items.map((item, index) => <li key={index}>{item.description?.value ?? "Description needs review"} · {item.line_total?.value ?? "Amount needs review"} ({item.line_total?.status ?? "missing"})</li>)}</ul></div> : null}
          {run?.validation_result && <div className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-950"><p className="font-medium">Extraction review signals</p><p>{run.validation_result.review_reasons?.join(", ") || "No deterministic consistency issue found; employee confirmation is still required."}</p><p className="mt-1">These checks are not policy findings or fraud decisions.</p></div>}
        </Card>;
      })}
      {expense && ["submitted", "in_review"].includes(expense.status) && <Card title="Record a human review decision" description="This changes workflow state only; it does not claim that policy evaluation passed.">
        <form onSubmit={(event) => void recordDecision(event)} className="flex flex-col gap-3 sm:flex-row">
          <label className="text-sm">Decision
            <select value={decisionAction} onChange={(event) => setDecisionAction(event.target.value as typeof decisionAction)} className="mt-1 block rounded-lg border border-[var(--color-border)] px-3 py-2">
              <option value="approve">Approve</option><option value="reject">Reject</option><option value="request_correction">Request correction</option><option value="escalate">Move to in review</option>
            </select>
          </label>
          <label className="flex-1 text-sm">Reason (required for rejection or correction)
            <input value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} className="mt-1 block w-full rounded-lg border border-[var(--color-border)] px-3 py-2" />
          </label>
          <button disabled={loading || (["reject", "request_correction"].includes(decisionAction) && !decisionReason.trim())} className="self-end rounded-lg bg-[var(--color-primary)] px-4 py-2 text-white disabled:opacity-50">Record decision</button>
        </form>
      </Card>}
      {receipts.length === 0 && !loading && <p className="text-sm text-[var(--color-text-muted)]">No authorized receipt records loaded.</p>}
    </>
  );
}
