/**
 * Shared Proofline API client.
 *
 * Every client - the employee Android app, the employee web portal and the internal
 * HR/Finance/Admin console - imports its types and its error handling from here. None of
 * them defines its own expense model, because three models would eventually disagree and
 * the disagreement would be invisible until an employee and a reviewer saw different
 * numbers for the same claim.
 *
 * Types come from `schema.d.ts`, generated from the backend's OpenAPI document by
 * `npm run api:generate`. Do not edit either generated file by hand.
 *
 * ---------------------------------------------------------------------------
 * WHAT THIS EXPORTS TODAY, AND WHY THE LIST IS SHORT
 *
 * The generated schema only contains types reachable from routes the backend actually
 * serves. This includes draft creation, private receipt upload/batches, authorized receipt
 * status/content and extraction-run results, plus health, metadata, identity and demo.
 *
 * The canonical claim DTOs - Expense, Money, Finding, Receipt, DuplicateCandidate,
 * ReviewDecision, the policy types - are defined and unit-tested in the backend
 * (app/schemas/*) but are NOT reachable yet, because their routes are not implemented.
 * They are therefore not exported here, and they are deliberately not stubbed with a
 * hand-written duplicate: a hand-written copy is exactly the "independent, conflicting
 * expense model" this package exists to prevent, and it would silently stop matching the
 * backend. They appear here automatically - with no edit to this file - as soon as their
 * routes exist and the generator is re-run.
 * ---------------------------------------------------------------------------
 */

import createFetchClient, { type Client } from "openapi-fetch";

import type { components, paths } from "./schema";

export type { components, paths };

/** The generated schema, aliased for convenience. */
export type Schemas = components["schemas"];

// ---------------------------------------------------------------------------
// Available now
// ---------------------------------------------------------------------------

export type HealthResponse = Schemas["HealthResponse"];
export type HealthComponent = Schemas["HealthComponent"];
export type ApiMetaResponse = Schemas["ApiMetaResponse"];
export type EnumCatalogueResponse = Schemas["EnumCatalogueResponse"];

export type Membership = Schemas["MembershipSummary"];
export type UserSummary = Schemas["UserSummary"];
export type RoleAssignment = Schemas["RoleAssignmentSummary"];

export type AuditEvent = Schemas["AuditEventResponse"];
export type AuditEventListResponse = Schemas["AuditEventListResponse"];

export type DemoSeedResponse = Schemas["DemoSeedResponse"];
export type DemoResetResponse = Schemas["DemoResetResponse"];

export type PageInfo = Schemas["PageInfo"];

/** Enum unions present in the served contract today. */
export type RoleCodeValue = Schemas["RoleCode"];
export type MembershipStatusValue = Schemas["MembershipStatus"];
export type AuditActorTypeValue = Schemas["AuditActorType"];

// Enum unions declared and tested in the backend but not yet in the generated schema,
// listed so the gap is explicit rather than surprising:
//
//   ExpenseStatus, ExpenseChannel, FindingResult, FindingSeverity, FindingStatus,
//   FindingType, DuplicateStatus, ReviewAction, RecommendedAction, FieldSource,
//   ExtractionStatus, LineItemEligibility, PolicyReviewState, ApprovalState,
//   ApprovalTaskStatus, StorageBackend, DerivationType, TripStatus, ExpenseFieldName

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

/** The single error envelope every failing response uses. */
export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: unknown[];
    request_id: string;
  };
}

/** Raised for any non-2xx response, carrying the parsed envelope when present. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly details: unknown[];

  constructor(options: {
    status: number;
    code: string;
    message: string;
    requestId?: string | null;
    details?: unknown[];
  }) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.requestId = options.requestId ?? null;
    this.details = options.details ?? [];
  }

  /**
   * Whether the caller should re-authenticate.
   *
   * 403 is deliberately NOT included: it means the identity is valid but lacks authority
   * (no active membership, or no permission). Re-authenticating will not help, and
   * treating it as "log in again" hides an authorization refusal from the user.
   */
  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403 || this.code === "FORBIDDEN";
  }

  /** A stale write: reload the record and let the user re-apply the change. */
  get isStaleVersion(): boolean {
    return this.code === "STALE_VERSION";
  }

  get isNotFound(): boolean {
    return this.status === 404 || this.code === "NOT_FOUND";
  }

  /**
   * A capability the contract describes but this build does not implement.
   *
   * Surfaced explicitly so a client can render "not available yet" instead of a generic
   * failure, which is the difference between an honest scaffold and a broken feature.
   */
  get isNotImplemented(): boolean {
    return this.status === 501 || this.code === "NOT_IMPLEMENTED";
  }

  /** The server refused a missing Idempotency-Key, or the key was reused. */
  get isIdempotencyProblem(): boolean {
    return this.code === "IDEMPOTENCY_CONFLICT";
  }
}

function isErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== "object" || value === null) return false;
  const candidate = (value as { error?: unknown }).error;
  return typeof candidate === "object" && candidate !== null && "code" in candidate;
}

/**
 * Turn an openapi-fetch response into either data or a thrown {@link ApiError}.
 *
 * Every call in every client goes through this, so an error envelope is never
 * accidentally rendered as data and the request id is always available for support.
 */
export async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await request;

  if (response.ok && error === undefined) {
    if (data === undefined) {
      throw new ApiError({
        status: response.status,
        code: "EMPTY_RESPONSE",
        message: "The server returned a success status with no body.",
        requestId: response.headers.get("x-request-id"),
      });
    }
    return data;
  }

  if (isErrorEnvelope(error)) {
    throw new ApiError({
      status: response.status,
      code: error.error.code,
      message: error.error.message,
      requestId: error.error.request_id,
      details: error.error.details,
    });
  }

  throw new ApiError({
    status: response.status,
    code: "UNEXPECTED_RESPONSE",
    message: "The server returned an unexpected response.",
    requestId: response.headers.get("x-request-id"),
  });
}

// ---------------------------------------------------------------------------
// Pagination
//
// The shape is documented in docs/api-contract.md section 4.3: `items` plus a `page`
// object carrying an opaque `next_cursor`. The cursor is opaque to clients by design, so
// that it can become a keyset cursor later with no client change.
// ---------------------------------------------------------------------------

export interface Page<T> {
  items: T[];
  page: PageInfo;
}

/**
 * Fetch every page of a list endpoint.
 *
 * Guarded against a server that returns a cursor without advancing: a malformed cursor
 * would otherwise loop forever and hammer the API.
 */
export async function fetchAllPages<T>(
  fetchPage: (cursor: string | null) => Promise<Page<T>>,
  options: { maxPages?: number } = {},
): Promise<T[]> {
  const maxPages = options.maxPages ?? 100;
  const collected: T[] = [];
  let cursor: string | null = null;
  const seen = new Set<string>();

  for (let page = 0; page < maxPages; page += 1) {
    const result = await fetchPage(cursor);
    collected.push(...result.items);
    const next = result.page.next_cursor;
    if (!next) break;
    if (seen.has(next)) {
      throw new Error("Pagination cursor did not advance; refusing to loop.");
    }
    seen.add(next);
    cursor = next;
  }

  return collected;
}

// ---------------------------------------------------------------------------
// Client factory
// ---------------------------------------------------------------------------

export interface ApiClientOptions {
  /**
   * API origin, for example `http://localhost:8000`. Generated paths include `/api/v1`.
   *
   * The versioned prefix is part of each generated OpenAPI path.
   */
  baseUrl: string;
  /** Supplies the Authorization header, or nothing in demo mode. */
  getToken?: () => string | null | undefined | Promise<string | null | undefined>;
  /**
   * Supplies the demo actor header.
   *
   * Demo mode identifies a USER, never a role: the server loads roles, permissions and
   * scope from its own database. A client-sent role is ignored by design, so there is
   * deliberately no option here to send one.
   */
  getDemoActorId?: () => string | null | undefined;
  /** Correlates a request with the server log line and the audit event. */
  getRequestId?: () => string | undefined;
  fetch?: typeof globalThis.fetch;
}

export type ProoflineClient = Client<paths>;

/** Build a typed client. */
export function createApiClient(options: ApiClientOptions): ProoflineClient {
  const client = createFetchClient<paths>({
    baseUrl: options.baseUrl.replace(/\/$/, ""),
    fetch: options.fetch,
  });

  client.use({
    onRequest({ request }) {
      const token = options.getToken?.();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);

      const demoActorId = options.getDemoActorId?.();
      if (demoActorId) request.headers.set("X-Demo-Actor-Id", demoActorId);

      const requestId = options.getRequestId?.();
      if (requestId) request.headers.set("X-Request-ID", requestId);

      return request;
    },
  });

  return client;
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

/**
 * Format a monetary amount for display.
 *
 * Amounts arrive as decimal strings precisely so that no float arithmetic happens on the
 * way to the screen. This function formats; it never computes, and it never sums.
 */
export function formatMoney(
  amount: { value?: string | null; currency?: string | null } | null | undefined,
  locale = "en-IN",
): string {
  if (!amount?.value) return "\u2014";
  const numeric = Number(amount.value);
  if (!Number.isFinite(numeric)) return `${amount.value} ${amount.currency ?? ""}`.trim();
  try {
    return new Intl.NumberFormat(locale, {
      style: amount.currency ? "currency" : "decimal",
      currency: amount.currency ?? undefined,
      minimumFractionDigits: 2,
    }).format(numeric);
  } catch {
    return `${amount.value} ${amount.currency ?? ""}`.trim();
  }
}

/**
 * Human-readable label for a known enum value.
 *
 * Deliberately an explicit map rather than a generic title-caser. Several values carry
 * product meaning that a generic transformation would destroy: `not_evaluated` means "no
 * rule has run yet" and must never read as "ineligible", and `email_simulated` is
 * demo-only and must not read as a real integration.
 */
const DISPLAY_LABELS: Record<string, string> = {
  email_simulated: "Simulated email (demo only)",
  needs_info: "Needs information",
  in_review: "Under review",
  not_evaluated: "Not yet checked",
  unknown: "Cannot be determined",
  request_correction: "Correction requested",
  receipt_extraction: "From the receipt",
  employee_input: "Entered by the employee",
  reviewer_correction: "Corrected by a reviewer",
  imported_data: "Imported",
  computed: "Calculated",
  finance_reviewer: "Finance reviewer",
  finance_admin: "Finance administrator",
  hr_reviewer: "HR reviewer",
  org_admin: "Organization administrator",
  policy_admin: "Policy administrator",
};

export function humanise(value: string | null | undefined): string {
  if (!value) return "\u2014";
  const known = DISPLAY_LABELS[value];
  if (known) return known;
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

/**
 * Employee-facing wording for a finding result.
 *
 * Never accusatory. UNKNOWN reads as "we could not confirm this yet", not as a suggestion
 * of wrongdoing.
 */
export function describeResult(result: string | null | undefined): string {
  switch (result) {
    case "PASS":
      return "Meets the policy";
    case "FAIL":
      return "Does not meet the policy";
    case "UNKNOWN":
      return "We could not confirm this claim yet";
    default:
      return result ? humanise(result) : "\u2014";
  }
}

/**
 * Employee-facing wording for a duplicate candidate.
 *
 * A candidate is a prompt for a human, never an accusation. That wording rule lives here
 * so no client invents its own.
 */
export function describeDuplicateStatus(status: string | null | undefined): string {
  switch (status) {
    case "open":
      return "Possibly submitted twice - a reviewer will check";
    case "confirmed":
      return "Confirmed by a reviewer as submitted twice";
    case "dismissed":
      return "Checked and confirmed as separate expenses";
    default:
      return humanise(status);
  }
}
