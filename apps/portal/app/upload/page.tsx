"use client";

import { useEffect, useMemo, useState } from "react";

import { Card, PageHeader } from "@/components/ui";
import { ApiError, unwrap, type components } from "@proofline/api-client";
import { API_BASE_URL, createPortalApi, readDemoActorId } from "@/lib/api";

type Receipt = components["schemas"]["ReceiptResponse"];
type UploadReceipt = components["schemas"]["ReceiptUploadResponse"];

const api = createPortalApi();
const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED = new Set(["image/jpeg", "image/png", "image/webp"]);

function labelStatus(status: string): string {
  return status.replaceAll("_", " ");
}

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [expenseId, setExpenseId] = useState<string | null>(null);
  const [draftKey, setDraftKey] = useState<string | null>(null);
  const [batchKey, setBatchKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  const hasActive = useMemo(
    () => receipts.some((receipt) => ["pending", "running"].includes(receipt.extraction_status)),
    [receipts],
  );

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
      if (!response.ok) throw new Error("Receipt content could not be opened.");
      const objectUrl = URL.createObjectURL(await response.blob());
      tab.location.href = objectUrl;
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (cause) {
      tab.close();
      setError(cause instanceof Error ? cause.message : "Receipt content could not be opened.");
    }
  }

  useEffect(() => {
    if (!expenseId || !hasActive) return;
    const timer = window.setInterval(() => setRefresh((value) => value + 1), 2000);
    return () => window.clearInterval(timer);
  }, [expenseId, hasActive]);

  useEffect(() => {
    if (!expenseId) return;
    let cancelled = false;
    void unwrap(api.GET("/api/v1/expenses/{expense_id}/receipts", { params: { path: { expense_id: expenseId } } }))
      .then((items) => {
        if (cancelled) return;
        setReceipts(items);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof ApiError ? cause.message : "Could not refresh receipt status.");
      });
    return () => { cancelled = true; };
  }, [expenseId, refresh]);

  async function startUpload() {
    setError(null);
    if (files.length === 0 || files.length > 20) {
      setError("Choose between 1 and 20 receipt images.");
      return;
    }
    const invalid = files.find((file) => !ACCEPTED.has(file.type) || file.size > MAX_BYTES || file.size === 0);
    if (invalid) {
      setError(`${invalid.name} must be a non-empty JPEG, PNG or WebP image up to 10 MiB.`);
      return;
    }
    setBusy(true);
    try {
      let targetExpenseId = expenseId;
      if (!targetExpenseId) {
        const key = draftKey ?? crypto.randomUUID();
        setDraftKey(key);
        const draft = await unwrap(api.POST("/api/v1/expenses", {
          params: { header: { "Idempotency-Key": key } },
          body: { channel: "web" },
        }));
        targetExpenseId = draft.id;
        setExpenseId(targetExpenseId);
        setDraftKey(null);
      }
      const key = batchKey ?? crypto.randomUUID();
      setBatchKey(key);
      const form = new FormData();
      for (const file of files) form.append("files", file, file.name);
      const uploaded = await unwrap(api.POST("/api/v1/expenses/{expense_id}/receipts/batch", {
        params: { path: { expense_id: targetExpenseId }, header: { "Idempotency-Key": key } },
        // The OpenAPI 3.1 schema models binary parts as contentMediaType strings.
        // Pass FormData at runtime so the browser supplies the multipart boundary.
        body: form as unknown as { files: string[] },
      }));
      setReceipts(uploaded.map((item: UploadReceipt) => item.receipt));
      setFiles([]);
      setBatchKey(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Upload failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function retryReceipt(receiptId: string) {
    setError(null);
    try {
      const updated = await unwrap(api.POST("/api/v1/receipts/{receipt_id}/extractions", {
        params: { path: { receipt_id: receiptId }, header: { "Idempotency-Key": crypto.randomUUID() } },
      }));
      setReceipts((current) => current.map((receipt) => receipt.id === receiptId ? updated : receipt));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Extraction retry could not be scheduled.");
    }
  }

  return (
    <>
      <PageHeader title="Add receipts" description="Upload up to 20 images. Each receipt is processed as its own task; uncertain values stay marked for your review." />
      <Card title="Choose receipt images" description="JPEG, PNG and WebP, up to 10 MiB each. The backend checks file contents before private storage.">
        <div className="space-y-4">
          <input
            aria-label="Receipt images"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={(event) => { setFiles(Array.from(event.target.files ?? [])); setBatchKey(null); }}
            className="block w-full text-sm"
          />
          {files.length > 0 && <p className="text-sm text-[var(--color-text-muted)]">{files.length} file(s) selected.</p>}
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <button type="button" disabled={busy || files.length === 0} onClick={() => void startUpload()} className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
            {busy ? "Uploading…" : "Create draft and upload"}
          </button>
        </div>
      </Card>
      {expenseId && <p className="text-sm text-[var(--color-text-muted)]">Draft expense {expenseId}</p>}
      {receipts.map((receipt) => {
        const run = receipt.extraction_runs?.at(-1);
        const result = run?.structured_result;
        return (
          <Card key={receipt.id} title={`Receipt ${receipt.id.slice(0, 8)}`} description={`Processing: ${labelStatus(receipt.extraction_status)}${run ? ` · ${run.provider}${run.model ? ` / ${run.model}` : ""}` : ""}`}>
            {result ? (
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                {(["merchant", "transaction_date", "currency", "grand_total"] as const).map((name) => {
                  const field = result[name];
                  if (!field) return null;
                  return <div key={name}><dt className="font-medium capitalize">{name.replaceAll("_", " ")}</dt><dd>{field.value ?? "Needs review"} <span className="text-[var(--color-text-muted)]">({labelStatus(field.status)})</span></dd></div>;
                })}
                {run?.validation_result?.human_review_required && <p className="sm:col-span-2 text-amber-800">Please verify the extracted values against the original receipt.</p>}
                {!!result.line_items?.length && <div className="sm:col-span-2"><h3 className="font-medium">Visible line items</h3><ul className="mt-2 space-y-1">{result.line_items.map((item, index) => <li key={index}>{item.description?.value ?? "Description needs review"} · {item.line_total?.value ?? "Amount needs review"} ({item.line_total?.status ?? "missing"})</li>)}</ul></div>}
              </dl>
            ) : run?.status === "failed" || run?.status === "unavailable" ? (
              <div><p role="status">Extraction {labelStatus(run.status)}. No receipt values were produced.</p><button type="button" className="mt-2 underline" onClick={() => void retryReceipt(receipt.id)}>Retry extraction</button></div>
            ) : <p role="status">Extraction is {labelStatus(run?.status ?? receipt.extraction_status)}.</p>}
            <button type="button" className="mt-4 inline-block underline" onClick={() => void openReceipt(receipt.content_url)}>Open receipt through the authorized API</button>
          </Card>
        );
      })}
    </>
  );
}
