/**
 * Live-client tests for the analytics access layer.
 *
 * `createApiClient` accepts a `fetch` override, so these tests exercise the real client -
 * real URL building, real header middleware, real error envelope parsing - against a stub
 * transport. Nothing here stubs `loadOverview` or `loadSpendPage`: the assertions are on
 * the HTTP requests that were actually issued and on what the layer returns from the
 * responses, which is what the dashboard consumes.
 */

import { describe, expect, it, vi } from "vitest";

import { createApiClient, unwrap, type ApiClientOptions } from "@proofline/api-client";

import {
  EMPTY_FILTERS,
  createRequestGate,
  describeError,
  loadFilterOptions,
  loadOverview,
  loadSpendPage,
  type AnalyticsError,
  type AnalyticsFilters,
} from "../src/lib/analytics";
import { EMPTY_OVERVIEW_FIXTURE, OVERVIEW_FIXTURE, spendResponse, spendRow } from "./analytics-fixtures";

const RANGE = { from: "2026-07-01", to: "2026-09-30" };
const RANGE_FILTERS: AnalyticsFilters = {
  ...EMPTY_FILTERS,
  departmentId: "11111111-1111-4111-8111-111111111111",
  employeeMembershipId: "44444444-4444-4444-8444-444444444444",
  status: "approved",
};

interface RecordedCall {
  url: string;
  headers: Headers;
  signal: AbortSignal | null | undefined;
}

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

function errorEnvelope(code: string, message: string, requestId: string) {
  return { error: { code, message, details: [], request_id: requestId } };
}

/** A stub transport that records every request and answers from a scenario. */
function stubTransport(
  responder: (call: RecordedCall) => Response | Promise<Response>,
): { calls: RecordedCall[]; fetch: typeof globalThis.fetch } {
  const calls: RecordedCall[] = [];
  const fetch: typeof globalThis.fetch = async (input, init) => {
    // openapi-fetch hands the middleware-processed Request straight to fetch, so the
    // headers and signal have to be read from whichever form the call arrives in.
    const request = input instanceof Request ? input : null;
    const call: RecordedCall = {
      url: request ? request.url : String(input),
      headers: request ? request.headers : new Headers(init?.headers),
      signal: init?.signal ?? request?.signal,
    };
    calls.push(call);
    return responder(call);
  };
  return { calls, fetch };
}

function client(overrides: Partial<ApiClientOptions> = {}) {
  return createApiClient({
    baseUrl: "http://api.test",
    getToken: () => null,
    getDemoActorId: () => null,
    ...overrides,
  });
}

/** Await a request that is expected to fail, and return the state the UI would render. */
async function describeFailure(pending: Promise<unknown>): Promise<AnalyticsError> {
  try {
    await pending;
  } catch (error) {
    return describeError(error);
  }
  throw new Error("Expected the request to fail, but it resolved.");
}

describe("overview requests", () => {
  it("issues a GET with the inclusive period and the selected filters", async () => {
    const { calls, fetch } = stubTransport(() => jsonResponse(OVERVIEW_FIXTURE));
    const api = client({ fetch });

    const overview = await loadOverview(api, {
      from: RANGE.from,
      to: RANGE.to,
      department_id: RANGE_FILTERS.departmentId,
      employee_membership_id: RANGE_FILTERS.employeeMembershipId,
      status: "approved",
    });

    expect(calls).toHaveLength(1);
    const requested = new URL(calls[0]!.url);
    expect(requested.pathname).toBe("/api/v1/analytics/overview");
    expect(requested.searchParams.get("from")).toBe("2026-07-01");
    expect(requested.searchParams.get("to")).toBe("2026-09-30");
    expect(requested.searchParams.get("department_id")).toBe(RANGE_FILTERS.departmentId);
    expect(requested.searchParams.get("employee_membership_id")).toBe(
      RANGE_FILTERS.employeeMembershipId,
    );
    expect(requested.searchParams.get("status")).toBe("approved");
    // Filters that were not selected are absent, not empty.
    expect(requested.searchParams.has("currency")).toBe(false);

    expect(overview.claim_count).toBe(1234);
    expect(overview.status_counts).toHaveLength(7);
  });

  it("asks for the unfiltered period when loading filter option lists", async () => {
    const { calls, fetch } = stubTransport(() => jsonResponse(OVERVIEW_FIXTURE));
    const api = client({ fetch });

    await loadFilterOptions(api, RANGE);

    const requested = new URL(calls[0]!.url);
    expect(requested.searchParams.get("from")).toBe("2026-07-01");
    expect(requested.searchParams.has("department_id")).toBe(false);
    expect(requested.searchParams.has("status")).toBe(false);
  });

  it("attaches the demo actor header when demo mode supplies an id", async () => {
    const { calls, fetch } = stubTransport(() => jsonResponse(OVERVIEW_FIXTURE));
    const api = client({ fetch, getDemoActorId: () => "99999999-9999-4999-8999-999999999999" });

    await loadOverview(api, { from: RANGE.from, to: RANGE.to });

    expect(calls[0]!.headers.get("x-demo-actor-id")).toBe("99999999-9999-4999-8999-999999999999");
    // The console never selects a role or an organization: only an actor identity.
    expect(calls[0]!.headers.get("authorization")).toBeNull();
    for (const header of calls[0]!.headers.keys()) {
      expect(header).not.toMatch(/role|organization|scope|permission/i);
    }
  });

  it("sends no credential when no token and no actor are configured", async () => {
    const { calls, fetch } = stubTransport(() => jsonResponse(OVERVIEW_FIXTURE));
    await loadOverview(client({ fetch }), { from: RANGE.from, to: RANGE.to });

    expect(calls[0]!.headers.get("authorization")).toBeNull();
    expect(calls[0]!.headers.get("x-demo-actor-id")).toBeNull();
  });

  it("parses an empty period without inventing a zero total", async () => {
    const { fetch } = stubTransport(() => jsonResponse(EMPTY_OVERVIEW_FIXTURE));
    const overview = await loadOverview(client({ fetch }), { from: RANGE.from, to: RANGE.to });

    expect(overview.claim_count).toBe(0);
    expect(overview.status_amounts).toEqual([]);
    expect(overview.claims_with_unknown_transaction_date).toBe(41);
  });
});

describe("spend requests and pagination", () => {
  it("requests one page with the grouping dimension, page limit and no cursor", async () => {
    const { calls, fetch } = stubTransport(() => jsonResponse(spendResponse()));
    const api = client({ fetch });

    const page = await loadSpendPage(api, {
      from: RANGE.from,
      to: RANGE.to,
      group_by: "department",
      limit: 200,
    });

    const requested = new URL(calls[0]!.url);
    expect(requested.pathname).toBe("/api/v1/analytics/spend");
    expect(requested.searchParams.get("group_by")).toBe("department");
    expect(requested.searchParams.get("limit")).toBe("200");
    expect(requested.searchParams.has("cursor")).toBe(false);
    expect(page.rows).toHaveLength(2);
    expect(page.page.total).toBe(2);
    expect(page.page.next_cursor).toBeNull();
  });

  it("reports a partial page as partial instead of the whole dataset", async () => {
    // 250 matching groups, 200 returned, a cursor for the rest: the caller can see that
    // what it holds is one page.
    const { fetch } = stubTransport(() =>
      jsonResponse(
        spendResponse({
          results: {
            items: [spendRow({ bucket_start: "2026-07-01" })],
            page: { limit: 200, next_cursor: "cursor-page-2", total: 250 },
          },
        }),
      ),
    );

    const page = await loadSpendPage(client({ fetch }), {
      from: RANGE.from,
      to: RANGE.to,
      group_by: "month",
      limit: 200,
    });

    expect(page.rows).toHaveLength(1);
    expect(page.page.total).toBe(250);
    expect(page.page.next_cursor).toBe("cursor-page-2");
    expect(page.rows.length).toBeLessThan(page.page.total ?? 0);
  });

  it("follows the returned cursor to a second page and merges it", async () => {
    const pages = [
      spendResponse({
        results: {
          items: [spendRow({ bucket_start: "2026-07-01", amount_total: "10.00" })],
          page: { limit: 200, next_cursor: "cursor-page-2", total: 2 },
        },
      }),
      spendResponse({
        results: {
          items: [spendRow({ bucket_start: "2026-08-01", amount_total: "20.00" })],
          page: { limit: 200, next_cursor: null, total: 2 },
        },
      }),
    ];
    let index = 0;
    const { calls, fetch } = stubTransport(() => jsonResponse(pages[index++] ?? pages[1]!));
    const api = client({ fetch });

    const first = await loadSpendPage(api, {
      from: RANGE.from,
      to: RANGE.to,
      group_by: "month",
      limit: 200,
    });
    const second = await loadSpendPage(api, {
      from: RANGE.from,
      to: RANGE.to,
      group_by: "month",
      limit: 200,
      cursor: first.page.next_cursor ?? undefined,
    });

    expect(new URL(calls[0]!.url).searchParams.has("cursor")).toBe(false);
    expect(new URL(calls[1]!.url).searchParams.get("cursor")).toBe("cursor-page-2");
    expect(first.rows.length + second.rows.length).toBe(2);
    expect(second.page.next_cursor).toBeNull();
  });

  it("surfaces the undated-claim count that the API excludes from groups", async () => {
    const { fetch } = stubTransport(() =>
      jsonResponse(spendResponse({ claims_with_unknown_transaction_date: 17 })),
    );
    const page = await loadSpendPage(client({ fetch }), {
      from: RANGE.from,
      to: RANGE.to,
      group_by: "month",
      limit: 200,
    });
    expect(page.unknownDateCount).toBe(17);
    expect(page.fromDate).toBe("2026-07-01");
    expect(page.toDate).toBe("2026-09-30");
  });
});

describe("failure handling", () => {
  it("maps a 401 to an unauthenticated state, not a forbidden one", async () => {
    const { fetch } = stubTransport(() =>
      jsonResponse(errorEnvelope("UNAUTHENTICATED", "No credentials.", "req-401"), 401, {
        "x-request-id": "req-401",
      }),
    );

    const error = await describeFailure(
      loadOverview(client({ fetch }), { from: RANGE.from, to: RANGE.to }),
    );

    expect(error.kind).toBe("unauthenticated");
    expect(error.requestId).toBe("req-401");
    expect(error.message).toMatch(/authenticated/);
  });

  it("maps a 403 to a forbidden state and does not advise signing in again", async () => {
    const { fetch } = stubTransport(() =>
      jsonResponse(
        errorEnvelope(
          "FORBIDDEN",
          "Employee-level analytics requires analytics:read_org.",
          "req-403",
        ),
        403,
      ),
    );

    const error = await describeFailure(
      loadSpendPage(client({ fetch }), {
        from: RANGE.from,
        to: RANGE.to,
        group_by: "employee",
        limit: 200,
      }),
    );

    expect(error.kind).toBe("forbidden");
    expect(error.title).toBe("Analytics access denied");
    expect(error.message).toMatch(/analytics:read_org/);
    // A 403 means the identity is known and simply lacks authority: re-authenticating
    // would not help, so the copy must not suggest it.
    expect(error.message).not.toMatch(/sign in/i);
  });

  it("maps a 422 filter rejection to a validation state with the message intact", async () => {
    const { fetch } = stubTransport(() =>
      jsonResponse(
        errorEnvelope(
          "VALIDATION_FAILED",
          "The selected department_id is not part of the active organization.",
          "req-422",
        ),
        422,
      ),
    );

    const error = await describeFailure(
      loadOverview(client({ fetch }), { from: RANGE.from, to: RANGE.to }),
    );

    expect(error.kind).toBe("validation");
    expect(error.message).toMatch(/not part of the active organization/);
  });

  it("maps a 500 to a server failure rather than an empty chart", async () => {
    const { fetch } = stubTransport(() =>
      jsonResponse(errorEnvelope("INTERNAL_ERROR", "Unhandled error.", "req-500"), 500),
    );

    const error = await describeFailure(
      loadOverview(client({ fetch }), { from: RANGE.from, to: RANGE.to }),
    );

    expect(error.kind).toBe("server");
    expect(error.message).toMatch(/shows nothing/);
  });

  it("maps an unreachable backend to a network failure", async () => {
    const fetch: typeof globalThis.fetch = () => Promise.reject(new TypeError("fetch failed"));

    const error = await describeFailure(
      loadOverview(client({ fetch }), { from: RANGE.from, to: RANGE.to }),
    );

    expect(error.kind).toBe("network");
    expect(error.requestId).toBeNull();
  });

  it("never returns an error envelope as if it were data", async () => {
    const { fetch } = stubTransport(() =>
      jsonResponse(errorEnvelope("FORBIDDEN", "Denied.", "req-403"), 403),
    );

    await expect(
      loadOverview(client({ fetch }), { from: RANGE.from, to: RANGE.to }),
    ).rejects.toMatchObject({ code: "FORBIDDEN", status: 403, requestId: "req-403" });
  });

  it("does not treat a success status with no body as data", async () => {
    // `unwrap` is shared by every client; a 200 with no payload must raise rather than
    // resolve to `undefined`, which would render as an empty dashboard.
    await expect(
      unwrap(
        Promise.resolve({
          response: new Response(null, { status: 200 }),
          data: undefined,
          error: undefined,
        }),
      ),
    ).rejects.toMatchObject({ code: "EMPTY_RESPONSE" });
  });
});

describe("cancellation and stale responses", () => {
  it("propagates the abort signal so a superseded request is actually cancelled", async () => {
    // The transport rejects the way a real fetch does when its signal aborts.
    const fetch: typeof globalThis.fetch = (input, init) => {
      const signal = init?.signal ?? (input instanceof Request ? input.signal : null);
      return new Promise<Response>((_resolve, reject) => {
        if (signal?.aborted) {
          reject(new DOMException("The operation was aborted.", "AbortError"));
          return;
        }
        signal?.addEventListener("abort", () =>
          reject(new DOMException("The operation was aborted.", "AbortError")),
        );
      });
    };

    const controller = new AbortController();
    const pending = loadOverview(
      client({ fetch }),
      { from: RANGE.from, to: RANGE.to },
      controller.signal,
    );
    controller.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  it("ignores the response of a request that is no longer the latest", () => {
    // Mirrors the guard the dashboard applies before writing state, with the responses
    // deliberately arriving out of order.
    const gate = createRequestGate();
    const applied: string[] = [];

    const firstRequest = gate.begin();
    const secondRequest = gate.begin();

    const applyResult = (token: number, label: string) => {
      if (!gate.isCurrent(token)) return;
      applied.push(label);
    };

    applyResult(secondRequest, "filters B");
    applyResult(firstRequest, "filters A");

    expect(applied).toEqual(["filters B"]);
    expect(gate.isCurrent(firstRequest)).toBe(false);
    expect(gate.isCurrent(secondRequest)).toBe(true);
  });

  it("keeps every superseding request distinct", () => {
    const gate = createRequestGate();
    const tokens = [gate.begin(), gate.begin(), gate.begin()];
    expect(new Set(tokens).size).toBe(3);
    expect(tokens.filter((token) => gate.isCurrent(token))).toHaveLength(1);
  });
});

describe("rapid filter changes", () => {
  it("applies only the newest response when a slow earlier request lands last", async () => {
    const pendingResponses: Array<(response: Response) => void> = [];
    const fetch: typeof globalThis.fetch = () =>
      new Promise<Response>((resolve) => {
        pendingResponses.push(resolve);
      });
    const api = client({ fetch });
    const gate = createRequestGate();
    const applied: string[] = [];

    const request = async (from: string) => {
      const token = gate.begin();
      const overview = await loadOverview(api, { from, to: RANGE.to });
      if (!gate.isCurrent(token)) return;
      applied.push(`${from} -> ${overview.from_date}`);
    };

    const slower = request("2026-07-01");
    const newer = request("2026-08-01");
    await vi.waitFor(() => expect(pendingResponses).toHaveLength(2));

    // The newer selection answers first, then the superseded one arrives late.
    pendingResponses[1]?.(jsonResponse({ ...OVERVIEW_FIXTURE, from_date: "2026-08-01" }));
    await newer;
    pendingResponses[0]?.(jsonResponse({ ...OVERVIEW_FIXTURE, from_date: "2026-07-01" }));
    await slower;

    expect(applied).toEqual(["2026-08-01 -> 2026-08-01"]);
  });
});
