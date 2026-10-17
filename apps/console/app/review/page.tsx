"use client";

import { useEffect, useState } from "react";

import { Card, PageHeader } from "@/components/ui";
import { ApiError, unwrap, type components } from "@proofline/api-client";
import { API_BASE_URL, createConsoleApi, readDemoActorId } from "@/lib/api";

type Receipt = components["schemas"]["ReceiptResponse"];
const api = createConsoleApi();

export default function ReviewQueuePage() {
  const [expenseId, setExpenseId] = useState("");
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const hasActiveRuns = receipts.some((receipt) => ["pending", "running"].includes(receipt.extraction_status));

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
      setReceipts(await unwrap(api.GET("/api/v1/expenses/{expense_id}/receipts", {
        params: { path: { expense_id: expenseId.trim() } },
      })));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not load the authorized receipt records.");
      setReceipts([]);
    } finally {
      setLoading(false);
    }
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
      const response = await fetch(`${API_BASE_URL}${contentUrl}`, { headers, cache: "no-store" });
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
      {receipts.length === 0 && !loading && <p className="text-sm text-[var(--color-text-muted)]">No authorized receipt records loaded.</p>}
    </>
  );
}
