"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Card, PageHeader } from "@/components/ui";
import { ApiError, unwrap, type components } from "@proofline/api-client";
import { API_BASE_URL, createPortalApi, readDemoActorId } from "@/lib/api";

type Expense = components["schemas"]["ExpenseResponse"];
type AuditEvent = components["schemas"]["AuditEventResponse"];
const api = createPortalApi();

export default function ExpenseDetailPage({ params }: { params: Promise<{ expenseId: string }> }) {
  const [expenseId, setExpenseId] = useState<string | null>(null);
  const [expense, setExpense] = useState<Expense | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [merchantDraft, setMerchantDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { void params.then(({ expenseId: id }) => setExpenseId(id)); }, [params]);
  const load = useCallback(async () => {
    if (!expenseId) return;
    setError(null);
    try {
      const [detail, history] = await Promise.all([
        unwrap(api.GET("/api/v1/expenses/{expense_id}", { params: { path: { expense_id: expenseId } } })),
        unwrap(api.GET("/api/v1/expenses/{expense_id}/audit", { params: { path: { expense_id: expenseId }, query: { limit: 50 } } })),
      ]);
      setExpense(detail);
      setMerchantDraft(detail.merchant.value ?? "");
      setEvents(history.items);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "This claim could not be loaded.");
    }
  }, [expenseId]);
  useEffect(() => { void load(); }, [load]);

  async function saveCorrection(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!expense) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await unwrap(api.PATCH("/api/v1/expenses/{expense_id}", {
        params: { path: { expense_id: expense.id }, header: { "Idempotency-Key": crypto.randomUUID() } },
        body: { expected_version: expense.version, merchant: merchantDraft },
      }));
      setExpense(updated);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "The correction could not be saved.");
    } finally { setSaving(false); }
  }

  async function submitCorrection() {
    if (!expense) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await unwrap(api.POST("/api/v1/expenses/{expense_id}/submit", {
        params: { path: { expense_id: expense.id }, header: { "Idempotency-Key": crypto.randomUUID() } },
        body: { expected_version: expense.version },
      }));
      setExpense(updated);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "The corrected claim could not be resubmitted.");
    } finally { setSaving(false); }
  }

  async function openReceipt(contentUrl: string) {
    setError(null);
    const tab = window.open("about:blank", "_blank");
    if (!tab) { setError("Allow pop-ups to open the authorized receipt."); return; }
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
      <PageHeader title="Your claim" description="Current values, evidence and the authorized claim history." />
      <p className="mb-4"><Link className="underline" href="/expenses">Back to your claims</Link></p>
      {error && <p role="alert" className="mb-4 text-sm text-red-700">{error}</p>}
      {!expense && !error && <Card title="Loading claim"><p className="text-sm">The backend is checking ownership and status.</p></Card>}
      {expense && <>
        <Card title={`${expense.merchant.value ?? "Expense"} · ${expense.status.replaceAll("_", " ")}`} description={`Version ${expense.version} · ${expense.expense_date.value ?? "Date missing"}`}>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="font-medium">Amount</dt><dd>{expense.amount.value ?? "Missing"} {expense.amount.currency ?? ""}</dd><dd className="text-xs text-[var(--color-text-muted)]">Source: {expense.amount.source ?? "not recorded"}</dd></div>
            <div><dt className="font-medium">Merchant source</dt><dd>{expense.merchant.source ?? "not recorded"}</dd></div>
            <div><dt className="font-medium">Category</dt><dd>{expense.category ?? "Not provided"}</dd></div>
            <div><dt className="font-medium">Business purpose</dt><dd>{expense.business_purpose ?? "Not provided"}</dd></div>
          </dl>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">Workflow status is separate from policy compliance. Policy results remain UNKNOWN until a verified policy is available.</p>
        </Card>
        {expense.status === "needs_info" && <Card title="Respond to the correction request" description="Your correction is saved as a new claim version. The original submission and reviewer request remain in history.">
          <form onSubmit={(event) => void saveCorrection(event)} className="flex flex-col gap-3 sm:flex-row">
            <label className="flex-1 text-sm">Merchant
              <input value={merchantDraft} onChange={(event) => setMerchantDraft(event.target.value)} maxLength={300} className="mt-1 block w-full rounded-lg border border-[var(--color-border)] px-3 py-2" />
            </label>
            <button disabled={saving || !merchantDraft.trim()} className="self-end rounded-lg bg-[var(--color-primary)] px-4 py-2 text-white disabled:opacity-50">{saving ? "Saving…" : "Save correction"}</button>
          </form>
          <button type="button" disabled={saving} onClick={() => void submitCorrection()} className="mt-3 underline disabled:opacity-50">Resubmit corrected claim</button>
        </Card>}
        <Card title="Receipts" description="Receipt content is streamed only after the backend authorizes the request.">
          {(expense.receipts ?? []).length ? <ul className="space-y-2 text-sm">{(expense.receipts ?? []).map((receipt) => <li key={receipt.id}><button className="underline" onClick={() => void openReceipt(receipt.content_url)}>Open authorized receipt</button> · {receipt.extraction_status} · {receipt.detected_mime_type ?? "unknown type"}</li>)}</ul> : <p className="text-sm">No receipt is attached.</p>}
        </Card>
        <Card title="Claim history">
          {events.length ? <ol className="space-y-3 text-sm">{events.map((event) => <li key={event.id} className="border-l-2 border-[var(--color-border)] pl-3"><p className="font-medium">{event.action.replaceAll(".", " ")}</p><p className="text-[var(--color-text-muted)]">{new Date(event.created_at).toLocaleString()} · {event.actor_label ?? event.actor_type}</p>{event.reason && <p className="mt-1">{event.reason}</p>}</li>)}</ol> : <p className="text-sm">No claim events are available.</p>}
        </Card>
      </>}
    </>
  );
}
