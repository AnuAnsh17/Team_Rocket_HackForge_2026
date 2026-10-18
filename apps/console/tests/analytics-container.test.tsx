/**
 * Container-level tests for the analytics dashboard.
 *
 * WHY THESE EXIST
 *
 * `analytics-view.test.tsx` renders the pure `AnalyticsView` through `react-dom/server`.
 * That is the right tool for "given this API response, what does the screen say", but it
 * never runs an effect and never handles a click, so none of the four defects this suite
 * covers could appear in it:
 *
 *   A. rows from the previous grouping rendered under the new grouping's label while a
 *      no-error refresh was in flight;
 *   B. the previous selection's `next_cursor` surviving a filter or grouping change, so
 *      "Load more groups" sent the new filters with the old cursor and skipped groups;
 *   C. period captions (the summary line and all four chart captions) taken from the live
 *      controls while the figures on screen came from the previous selection;
 *   D. an invalid period leaving the previous figures on screen, unlabelled, with the
 *      error cleared.
 *
 * All four are effect-and-interaction behaviour, so these tests mount the real
 * `AnalyticsDashboard`, let its effects run, and drive it through the DOM.
 *
 * WHAT IS MOCKED
 *
 * Only the two request functions and the catalogue request are replaced, through
 * `vi.mock` on the access module. The real query builders (`buildOverviewQuery`,
 * `buildSpendQuery`, `buildFilterOptionsQuery`) are kept, so the query objects these tests
 * assert on are the ones the dashboard actually sends. Nothing in `src/` is stubbed.
 *
 * THE ENVIRONMENT
 *
 * The workspace has no `jsdom`, no `happy-dom` and no `@testing-library/react`, and this
 * work may not add dependencies, so `./analytics-dom` supplies the small DOM surface
 * `react-dom/client` needs. It must be installed BEFORE `react-dom/client` is imported:
 * `react-dom` decides at import time whether a DOM exists. Hence `installDom()` runs at
 * module scope and `react-dom/client` and the dashboard (which imports `react` and the UI
 * kit) are loaded dynamically after it.
 */

import { act, createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  chooseOption,
  click,
  findAll,
  findButton,
  findLabelled,
  installDom,
  setInputValue,
  textOf,
  type ShimElement,
  type ShimNode,
} from "./analytics-dom";
import { OVERVIEW_FIXTURE, pageInfo, spendRow } from "./analytics-fixtures";
import {
  initialDateRange,
  type AnalyticsGroupBy,
  type AnalyticsOverview,
  type DateRange,
  type OverviewQuery,
  type SpendPage,
  type SpendQuery,
} from "@/lib/analytics";

// ---------------------------------------------------------------------------
// Environment: DOM first, then React DOM, then the component under test.
// ---------------------------------------------------------------------------

const dom = installDom();
const { createRoot } = await import("react-dom/client");
const { default: AnalyticsDashboard, formatPeriodLabel } = await import(
  "@/components/AnalyticsDashboard"
);

/** The debounce the component applies to the free-text membership field. */
const FILTER_DEBOUNCE_MS = 400;

/** The period the dashboard opens with, recomputed the same way the component does. */
const RANGE: DateRange = initialDateRange();
/** A second, different but equally valid period: the first day of the current month. */
const OTHER_END = `${RANGE.to.slice(0, 7)}-01`;
const RANGE_B: DateRange = { from: RANGE.from, to: OTHER_END };

type RequestKind = "overview" | "catalogue" | "spend";
interface RecordedRequest {
  kind: RequestKind;
  query: Record<string, unknown>;
}

type Handler = (query: Record<string, unknown>) => Promise<unknown>;

/**
 * The request recorder and the per-test reply handlers. `vi.hoisted` so the `vi.mock`
 * factory above the imports can close over them safely.
 */
const api = vi.hoisted(() => ({
  requests: [] as RecordedRequest[],
  overview: null as Handler | null,
  catalogue: null as Handler | null,
  spend: null as Handler | null,
}));

vi.mock("@/lib/analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analytics")>();
  return {
    ...actual,
    // Mocked at the narrowest seam: the recorder sees the exact query object the
    // dashboard builds with the real builders.
    loadOverview: (_client: unknown, query: OverviewQuery) => {
      api.requests.push({ kind: "overview", query: { ...query } });
      const handler = api.overview;
      if (!handler) return Promise.reject(new Error("no overview handler installed"));
      return handler({ ...query }) as Promise<AnalyticsOverview>;
    },
    loadFilterOptions: (_client: unknown, range: DateRange) => {
      api.requests.push({
        kind: "catalogue",
        query: { ...actual.buildFilterOptionsQuery(range) },
      });
      const handler = api.catalogue;
      if (!handler) return Promise.reject(new Error("no catalogue handler installed"));
      return handler({ ...range }) as Promise<AnalyticsOverview>;
    },
    loadSpendPage: (_client: unknown, query: SpendQuery) => {
      api.requests.push({ kind: "spend", query: { ...query } });
      const handler = api.spend;
      if (!handler) return Promise.reject(new Error("no spend handler installed"));
      return handler({ ...query }) as Promise<SpendPage>;
    },
  };
});

// ---------------------------------------------------------------------------
// Fixtures and small helpers
// ---------------------------------------------------------------------------

const SPEND_ROWS = [
  spendRow({
    bucket_start: "2026-07-01",
    currency: "INR",
    claim_count: 40,
    amount_claim_count: 39,
    amount_total: "40000.00",
  }),
  spendRow({
    bucket_start: "2026-08-01",
    currency: "INR",
    claim_count: 50,
    amount_claim_count: 50,
    amount_total: "120000.50",
  }),
];

function spendPage(
  rows = SPEND_ROWS,
  page = pageInfo({ total: rows.length }),
  unknownDateCount = 0,
  groupBy: AnalyticsGroupBy = "month",
): SpendPage {
  return {
    rows,
    page,
    unknownDateCount,
    groupBy,
    fromDate: RANGE.from,
    toDate: RANGE.to,
  };
}

/**
 * The overview answers for the period it was asked about, the way the real endpoint
 * echoes the range it confirmed. That is what makes a caption taken from the wrong
 * selection visibly contradictory rather than merely different.
 */
function overviewFor(query: Record<string, unknown>): AnalyticsOverview {
  return { ...OVERVIEW_FIXTURE, from_date: String(query.from), to_date: String(query.to) };
}

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let settleResolve: ((value: T) => void) | undefined;
  let settleReject: ((error: unknown) => void) | undefined;
  const promise = new Promise<T>((resolve, reject) => {
    settleResolve = resolve;
    settleReject = reject;
  });
  return {
    promise,
    resolve: (value) => settleResolve?.(value),
    reject: (error) => settleReject?.(error),
  };
}

function respond(resource: "overview" | "catalogue" | "spend", value: unknown): void {
  api[resource] = () =>
    value instanceof Error ? Promise.reject(value) : Promise.resolve(value);
}

/**
 * Answer this resource from a promise the test controls. Parameterised on the promise
 * alone so a `Deferred<T>` of any response type can be passed.
 */
function answerWithDeferred(
  resource: "overview" | "catalogue" | "spend",
  reply: { promise: Promise<unknown> },
): void {
  api[resource] = () => reply.promise;
}

function requestsOfKind(kind: RequestKind): Array<Record<string, unknown>> {
  return api.requests.filter((entry) => entry.kind === kind).map((entry) => entry.query);
}

function countOf(kind: RequestKind): number {
  return api.requests.filter((entry) => entry.kind === kind).length;
}

let container: ShimElement;
let root: { render: (node: ReturnType<typeof createElement>) => void; unmount: () => void };

/** The text of the `<section>` card that carries the given heading. */
function cardText(title: string): string {
  const heading = findAll(
    container,
    (element) => element.localName === "h2" && element.textContent.trim() === title,
  )[0];
  if (!heading) throw new Error(`no card titled "${title}" was rendered`);
  let node: ShimNode | null = heading.parentNode;
  while (node && node.nodeName !== "SECTION") node = node.parentNode;
  if (!node) throw new Error(`no section encloses "${title}"`);
  return node.textContent;
}

function buttonOrNull(label: string): ShimElement | null {
  return (
    findAll(
      container,
      (element) => element.localName === "button" && element.textContent.trim() === label,
    )[0] ?? null
  );
}

/** Let pending promises settle and run any debounce the component has scheduled. */
async function settle(): Promise<void> {
  await act(async () => {
    vi.advanceTimersByTime(FILTER_DEBOUNCE_MS + 50);
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function mount(): Promise<void> {
  container = dom.document.createElement("div");
  dom.document.body.appendChild(container);
  root = createRoot(container as unknown as Element);
  await act(async () => {
    root.render(createElement(AnalyticsDashboard));
  });
  await settle();
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  api.requests.length = 0;
  api.overview = (query) => Promise.resolve(overviewFor(query));
  api.catalogue = () => Promise.resolve(OVERVIEW_FIXTURE);
  api.spend = () => Promise.resolve(spendPage());
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  vi.useRealTimers();
  api.overview = null;
  api.catalogue = null;
  api.spend = null;
});

// ---------------------------------------------------------------------------
// A. Grouping change while the previous request is unresolved
// ---------------------------------------------------------------------------

describe("A: a grouping change never relabels the previous grouping's rows", () => {
  it("shows a loading state instead of month rows under an employee grouping", async () => {
    await mount();
    expect(cardText("Filtered spend groups")).toContain("Jul 2026");

    // The employee-grouped page never resolves, so the only rows available are the month
    // rows from the previous selection.
    const pending = deferred<SpendPage>();
    answerWithDeferred("spend", pending);
    await act(async () => {
      chooseOption(findLabelled(container, "Spend grouping dimension"), "employee");
    });
    await settle();

    const spendCard = cardText("Filtered spend groups");
    expect(spendCard).not.toContain("Employee name not recorded");
    expect(spendCard).not.toContain("Jul 2026");
    expect(spendCard).toContain("Loading spend groups");

    // The new grouping was requested, for the same period and filters, without a cursor.
    const spendQueries = requestsOfKind("spend");
    expect(spendQueries).toHaveLength(2);
    expect(spendQueries[1]).toMatchObject({
      from: RANGE.from,
      to: RANGE.to,
      group_by: "employee",
      limit: 200,
    });
    expect(spendQueries[1]?.cursor).toBeUndefined();

    // When it arrives, the employee rows are labelled as employees.
    await act(async () => {
      pending.resolve(
        spendPage(
          [
            spendRow({
              employee_membership_id: "33333333-3333-4333-8333-333333333333",
              employee_display_name: "Aditi Rao",
              amount_total: "10.00",
            }),
          ],
          pageInfo({ total: 1 }),
          0,
          "employee",
        ),
      );
    });
    expect(cardText("Filtered spend groups")).toContain("Aditi Rao");
  });
});

// ---------------------------------------------------------------------------
// B. Pagination cursor leakage
// ---------------------------------------------------------------------------

describe("B: a cursor never survives the selection it belongs to", () => {
  it("refuses to load more with the previous selection's cursor after a filter change", async () => {
    respond("spend", spendPage(SPEND_ROWS, pageInfo({ total: 5, next_cursor: "page-2" })));
    await mount();
    const loadMoreButton = findButton(container, "Load more groups");

    // The next selection's first page is unresolved, so nothing may be appended to it.
    const pending = deferred<SpendPage>();
    answerWithDeferred("spend", pending);
    await act(async () => {
      chooseOption(findLabelled(container, "Category"), "travel");
    });
    await settle();

    // The button is gone while the selection it belonged to is not on screen...
    expect(buttonOrNull("Load more groups")).toBeNull();
    // ...and even the node React unmounted cannot send the old cursor.
    click(loadMoreButton);
    await settle();

    const spendQueries = requestsOfKind("spend");
    expect(spendQueries.some((query) => query.cursor === "page-2")).toBe(false);
    const latest = spendQueries[spendQueries.length - 1];
    expect(latest).toMatchObject({ category: "travel", group_by: "month" });
    expect(latest?.cursor).toBeUndefined();

    await act(async () => {
      pending.resolve(spendPage(SPEND_ROWS, pageInfo({ total: 2 }), 0, "month"));
    });
    expect(cardText("Filtered spend groups")).toContain("showing 2 of 2 matching groups");
  });

  it("does not offer more groups while a same-selection refresh is unresolved", async () => {
    respond("spend", spendPage(SPEND_ROWS, pageInfo({ total: 2, next_cursor: "page-2" })));
    await mount();
    const loadMoreButton = findButton(container, "Load more groups");

    // Refreshing the same selection keeps the rows on screen...
    const pending = deferred<SpendPage>();
    answerWithDeferred("spend", pending);
    await act(async () => {
      click(findButton(container, "Refresh data"));
    });
    await settle();
    expect(cardText("Filtered spend groups")).toContain(
      "Updating these groups for the current selection.",
    );

    // ...but the first request for this selection is unresolved, so the cursor for it is
    // not followed yet.
    const before = countOf("spend");
    click(loadMoreButton);
    await settle();
    expect(countOf("spend")).toBe(before);
    expect(requestsOfKind("spend").some((query) => query.cursor === "page-2")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// C. Period captions
// ---------------------------------------------------------------------------

describe("C: period captions describe the response on screen", () => {
  it("keeps the caption and the API's confirmation on the period they belong to", async () => {
    await mount();
    expect(textOf(container)).toContain(`Period: ${formatPeriodLabel(RANGE)}`);
    expect(textOf(container)).toContain(
      `The API confirmed this period as ${RANGE.from} to ${RANGE.to}.`,
    );

    const pendingOverview = deferred<AnalyticsOverview>();
    const pendingSpend = deferred<SpendPage>();
    answerWithDeferred("overview", pendingOverview);
    answerWithDeferred("spend", pendingSpend);
    await act(async () => {
      setInputValue(findLabelled(container, "End date (inclusive)"), RANGE_B.to);
    });
    await settle();

    const rendered = textOf(container);
    // The controls have moved on...
    expect(findLabelled(container, "End date (inclusive)").value).toBe(RANGE_B.to);
    // ...but every caption still belongs to the response that is actually displayed, and
    // the summary says so rather than letting the controls speak for the figures.
    expect(rendered).toContain(`Period: ${formatPeriodLabel(RANGE)}`);
    expect(rendered).not.toContain(`Period: ${formatPeriodLabel(RANGE_B)}`);
    expect(rendered).toContain(
      `The API confirmed this period as ${RANGE.from} to ${RANGE.to}.`,
    );
    expect(rendered).toContain("which is the response on screen");
    expect(rendered).toContain(`Period: ${formatPeriodLabel(RANGE)} · amounts are never`);

    await act(async () => {
      pendingOverview.resolve(overviewFor({ from: RANGE_B.from, to: RANGE_B.to }));
      pendingSpend.resolve(spendPage());
    });
    await settle();
    expect(textOf(container)).toContain(`Period: ${formatPeriodLabel(RANGE_B)}`);
  });

  it("does not caption a failed refresh's retained figures with the new period", async () => {
    await mount();

    respond("overview", new Error("the analytics service did not respond"));
    respond("spend", new Error("the analytics service did not respond"));
    await act(async () => {
      setInputValue(findLabelled(container, "End date (inclusive)"), RANGE_B.to);
    });
    await settle();

    const rendered = textOf(container);
    expect(rendered).toContain("Backend unreachable");
    // The retained response is for the previous period, so that is what the caption says,
    // and the summary states that it is not what the controls now request.
    expect(rendered).toContain(`Period: ${formatPeriodLabel(RANGE)}`);
    expect(rendered).not.toContain(`Period: ${formatPeriodLabel(RANGE_B)}`);
    expect(rendered).toContain(
      `The API confirmed this period as ${RANGE.from} to ${RANGE.to}.`,
    );
    expect(rendered).toContain("which is the response on screen");
    // No figure from the previous period is presented as the failed selection's answer.
    expect(cardText("Filtered spend groups")).not.toContain("40,000.00");
  });
});

// ---------------------------------------------------------------------------
// D. Invalid selection
// ---------------------------------------------------------------------------

describe("D: an invalid selection asks for nothing and claims nothing", () => {
  it("issues no request and labels the retained figures with the period they belong to", async () => {
    await mount();
    const before = {
      overview: countOf("overview"),
      catalogue: countOf("catalogue"),
      spend: countOf("spend"),
    };

    await act(async () => {
      setInputValue(findLabelled(container, "Start date (inclusive)"), "2099-12-31");
    });
    await settle();

    const rendered = textOf(container);
    expect(rendered).toContain("This selection cannot be requested");
    expect(rendered).toContain("The start date must be on or before the end date.");
    expect(rendered).toContain("No request was sent");
    // The figures still on screen are labelled with the selection they belong to, not with
    // the impossible one in the controls.
    expect(rendered).toContain(`Period: ${formatPeriodLabel(RANGE)}`);
    expect(rendered).not.toContain("31 Dec 2099");
    expect(rendered).toContain("which is the response on screen");
    expect(cardText("Filtered spend groups")).toContain(
      "No request was sent for the selection now in the controls",
    );

    // Not one request, of any kind, was issued for the invalid selection.
    expect(countOf("overview")).toBe(before.overview);
    expect(countOf("catalogue")).toBe(before.catalogue);
    expect(countOf("spend")).toBe(before.spend);
    for (const entry of api.requests) {
      expect(entry.query.from).not.toBe("2099-12-31");
    }
  });

  it("restores a valid period and re-requests it when reset is used", async () => {
    await mount();
    await act(async () => {
      setInputValue(findLabelled(container, "Start date (inclusive)"), "2099-12-31");
    });
    await settle();
    expect(textOf(container)).toContain("This selection cannot be requested");

    const before = { overview: countOf("overview"), spend: countOf("spend") };
    await act(async () => {
      click(findButton(container, "Reset period and filters"));
    });
    await settle();

    const rendered = textOf(container);
    expect(rendered).not.toContain("This selection cannot be requested");
    expect(findLabelled(container, "Start date (inclusive)").value).toBe(RANGE.from);
    expect(rendered).toContain(`Period: ${formatPeriodLabel(RANGE)}`);
    expect(countOf("overview")).toBe(before.overview + 1);
    expect(countOf("spend")).toBe(before.spend + 1);
    const latest = requestsOfKind("spend")[countOf("spend") - 1];
    expect(latest).toMatchObject({ from: RANGE.from, to: RANGE.to, group_by: "month" });
    expect(latest?.category).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Pagination and request bookkeeping
// ---------------------------------------------------------------------------

describe("pagination follows the page it was offered for", () => {
  it("loads the next page with the cursor the first page returned", async () => {
    respond("spend", spendPage(SPEND_ROWS, pageInfo({ total: 3, next_cursor: "page-2" })));
    await mount();
    expect(cardText("Filtered spend groups")).toContain("showing 2 of 3 matching groups");

    respond(
      "spend",
      spendPage(
        [
          spendRow({
            bucket_start: "2026-09-01",
            claim_count: 5,
            amount_claim_count: 5,
            amount_total: "5000.00",
          }),
        ],
        pageInfo({ total: 3, next_cursor: null }),
      ),
    );
    await act(async () => {
      click(findButton(container, "Load more groups"));
    });
    await settle();

    const spendQueries = requestsOfKind("spend");
    expect(spendQueries).toHaveLength(2);
    expect(spendQueries[1]).toMatchObject({
      cursor: "page-2",
      from: RANGE.from,
      to: RANGE.to,
      group_by: "month",
      limit: 200,
    });

    const spendCard = cardText("Filtered spend groups");
    expect(spendCard).toContain("Sept 2026");
    expect(spendCard).toContain("across 2 pages");
    expect(buttonOrNull("Load more groups")).toBeNull();
  });
});

describe("request counts and query parameters", () => {
  it("sends exactly the requests each control change implies, with the right parameters", async () => {
    await mount();

    // One period load: the filtered overview, the unfiltered catalogue, and page one.
    expect(api.requests.map((entry) => entry.kind)).toEqual([
      "overview",
      "catalogue",
      "spend",
    ]);
    expect(requestsOfKind("overview")[0]).toMatchObject({ from: RANGE.from, to: RANGE.to });
    expect(requestsOfKind("overview")[0]?.department_id).toBeUndefined();
    expect(requestsOfKind("overview")[0]?.currency).toBeUndefined();
    expect(requestsOfKind("spend")[0]).toMatchObject({
      from: RANGE.from,
      to: RANGE.to,
      group_by: "month",
      limit: 200,
    });
    expect(requestsOfKind("spend")[0]?.cursor).toBeUndefined();

    // A grouping change re-requests the spend page only.
    await act(async () => {
      chooseOption(findLabelled(container, "Spend grouping dimension"), "department");
    });
    await settle();
    expect(countOf("overview")).toBe(1);
    expect(countOf("catalogue")).toBe(1);
    expect(countOf("spend")).toBe(2);
    expect(requestsOfKind("spend")[1]).toMatchObject({ group_by: "department" });
    expect(requestsOfKind("spend")[1]?.cursor).toBeUndefined();

    // A filter change re-requests both sections, carrying the filter, and starts at page
    // one again.
    await act(async () => {
      chooseOption(findLabelled(container, "Currency"), "INR");
    });
    await settle();
    expect(countOf("overview")).toBe(2);
    expect(countOf("catalogue")).toBe(2);
    expect(countOf("spend")).toBe(3);
    expect(requestsOfKind("overview")[1]).toMatchObject({
      from: RANGE.from,
      to: RANGE.to,
      currency: "INR",
    });
    expect(requestsOfKind("spend")[2]).toMatchObject({
      currency: "INR",
      group_by: "department",
      from: RANGE.from,
      to: RANGE.to,
    });
    expect(requestsOfKind("spend")[2]?.cursor).toBeUndefined();
    expect(requestsOfKind("spend")[2]?.category).toBeUndefined();
  });
});
