"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Card, PageHeader } from "@/components/ui";
import { ApiError, unwrap, type components } from "@proofline/api-client";
import { createPortalApi } from "@/lib/api";

type Expense = components["schemas"]["ExpenseSummary"];
const api = createPortalApi();

export default function MyExpensesPage() {
  const [items, setItems] = useState<Expense[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void unwrap(api.GET("/api/v1/expenses", { params: { query: { limit: 50 } } }))
      .then((page) => setItems(page.items))
      .catch((cause: unknown) => {
        setError(cause instanceof ApiError ? cause.message : "Your claims could not be loaded.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <PageHeader title="My expenses" description="Your claims and their current workflow status." />
      {error && <p role="alert" className="mb-4 text-sm text-red-700">{error}</p>}
      {loading ? (
        <Card title="Loading claims"><p className="text-sm">The backend is checking your authorized claims.</p></Card>
      ) : items.length ? (
        <div className="space-y-3">
          {items.map((expense) => (
            <Link key={expense.id} href={`/expenses/${expense.id}`} className="block rounded-xl focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]">
              <Card title={expense.merchant ?? "Expense"} description={`${expense.status.replaceAll("_", " ")} · ${expense.expense_date ?? "Date missing"}`}>
                <p className="text-sm">{expense.amount.value ?? "Amount missing"} {expense.amount.currency ?? ""}</p>
                <p className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">{expense.id}</p>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <Card title="No claims yet"><p className="text-sm text-[var(--color-text-muted)]">Create a draft from receipt capture to start a claim.</p></Card>
      )}
    </>
  );
}
