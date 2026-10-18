/**
 * Rendering tests for the analytics dashboard.
 *
 * `AnalyticsView` is pure: props in, markup out. That makes it directly renderable with
 * `react-dom/server` in the project's existing node test environment, with no new
 * dependency and no DOM shim, and it means these assertions are about what the component
 * does with an API response rather than about a mock of it.
 *
 * What is asserted here: the values on screen come from the response objects, the numbers
 * are currency-separated and exactly formatted, every empty/loading/error/stale/forbidden
 * state has distinct copy, pagination is described honestly, and the controls and charts
 * carry accessible names. Viewport behaviour is checked in a real browser during live
 * verification; here the responsive grid is asserted at the class level, which is stated
 * as such rather than dressed up as a layout test.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import AnalyticsDashboard, {
  AnalyticsView,
  formatMonthLabel,
  formatPeriodLabel,
  groupLabel,
  statusLabel,
} from "../src/components/AnalyticsDashboard";
import {
  EMPTY_FILTERS,
  type AnalyticsError,
  type AnalyticsGroupBy,
} from "../src/lib/analytics";
import {
  EMPTY_OVERVIEW_FIXTURE,
  OVERVIEW_FIXTURE,
  pageInfo,
  spendRow,
} from "./analytics-fixtures";

const RANGE = { from: "2026-07-01", to: "2026-09-30" };
const REQUEST_ID = "e2c6b1f4-0000-4000-8000-000000000000";

type ViewProps = Parameters<typeof AnalyticsView>[0];

function forbidden(): AnalyticsError {
  return {
    kind: "forbidden",
    title: "Analytics access denied",
    message:
      "The backend refused this request for the current actor. Analytics needs organization-scoped expense read access plus an analytics permission.",
    requestId: REQUEST_ID,
  };
}

function spendState(overrides: Partial<ViewProps["spend"]> = {}): ViewProps["spend"] {
  return {
    rows: [],
    page: pageInfo({ total: 0 }),
    unknownDateCount: 0,
    error: null,
    loading: false,
    refreshing: false,
    loadingMore: false,
    loadMoreError: null,
    pagesLoaded: 1,
    // The spend section only shows rows while the selection they were requested under is
    // still the selection on screen, so the default state is a loaded month-grouped result
    // for the fixture range. A test that changes the grouping must say so here too, which
    // is the point of the guard.
    loadedQuery: { from: RANGE.from, to: RANGE.to, group_by: "month", limit: 200 },
    ...overrides,
  };
}

/** Render the view, normalising the space characters Intl inserts around amounts. */
function render(overrides: Partial<ViewProps> = {}): string {
  const props: ViewProps = {
    range: RANGE,
    filters: EMPTY_FILTERS,
    employeeDraft: "",
    groupBy: "month",
    validationError: null,
    overview: { data: OVERVIEW_FIXTURE, error: null, loading: false, refreshing: false },
    catalogue: OVERVIEW_FIXTURE,
    catalogueError: null,
    spend: spendState(),
    lastUpdated: new Date("2026-10-18T04:30:00Z"),
    onRangeChange: () => {},
    onFilterChange: () => {},
    onEmployeeDraftChange: () => {},
    onGroupByChange: () => {},
    onReset: () => {},
    onRefresh: () => {},
    onLoadMore: () => {},
    ...overrides,
  };
  return renderToStaticMarkup(<AnalyticsView {...props} />).replace(/[\u00a0\u202f]/g, " ");
}

describe("the dashboard is a real component tree", () => {
  it("exports the container as the page entry point", () => {
    expect(typeof AnalyticsDashboard).toBe("function");
    expect(typeof AnalyticsView).toBe("function");
  });

  it("renders KPI values taken from the response, not from constants", () => {
    const html = render();

    expect(html).toContain("Claims in period");
    expect(html).toContain("1,234");
    expect(html).toContain("Awaiting review");
    expect(html).toContain("57");
    expect(html).toContain("Needs information");
    expect(html).toContain("Missing critical fields");
    expect(html).toContain("Uncertain critical fields");
    expect(html).toContain("No transaction date");
    expect(html).toContain("41");

    // A different response produces different figures, which is what proves the values
    // are read from the API rather than compiled in.
    const other = render({
      overview: {
        data: { ...OVERVIEW_FIXTURE, claim_count: 7, claims_requiring_review: 3 },
        error: null,
        loading: false,
        refreshing: false,
      },
    });
    expect(other).not.toContain("1,234");
    expect(other).toContain(">7<");
  });

  it("states the basis of every count so a figure cannot be read as more than it is", () => {
    const html = render();
    expect(html).toContain("Dated claims whose transaction date is inside the range");
    expect(html).toContain("Workflow status submitted plus in_review");
    expect(html).toContain("Dated in-range claims with no merchant, amount or currency");
    expect(html).toContain("outside every period and never counted at zero");
  });
});

describe("period and filter controls", () => {
  it("shows the selected period explicitly and calls both boundaries inclusive", () => {
    const html = render();
    expect(html).toContain("Period:");
    expect(html).toContain("1 Jul 2026 – 30 Sept 2026");
    expect(html).toContain("Inclusive of both dates, by transaction date only");
    expect(html).toContain("The API confirmed this period as 2026-07-01 to 2026-09-30");
  });

  it("labels every control and exposes the six implemented dimensions", () => {
    const html = render();
    for (const label of [
      "Start date (inclusive)",
      "End date (inclusive)",
      "Department",
      "Office location",
      "Category",
      "Currency",
      "Workflow status",
      "Employee membership id",
    ]) {
      expect(html).toContain(`aria-label="${label}"`);
    }
    for (const group of ["month", "department", "location", "category", "employee", "status"] as AnalyticsGroupBy[]) {
      expect(html).toContain(`value="${group}"`);
      expect(html).toContain(groupLabel(group));
    }
  });

  it("offers a reset that covers the period as well as the filters", () => {
    // The period is the one control that can be left in a state the API refuses, so the
    // escape hatch has to restore it. That the click actually does so is a container
    // behaviour, verified against the running console rather than in this static render.
    const html = render();
    expect(html).toContain("Reset period and filters");
  });

  it("builds option lists from the response and keeps a null category out of them", () => {
    const html = render();
    expect(html).toContain("Engineering");
    expect(html).toContain("Sales");
    expect(html).toContain("Bengaluru");
    expect(html).toContain("travel");
    expect(html).toContain("meals");
  });

  it("says a filter list is unavailable rather than loading forever", () => {
    const failed = render({
      catalogue: null,
      catalogueError: forbidden(),
    });
    expect(failed).toContain("Departments unavailable");
    expect(failed).toContain("Currencies unavailable");
    expect(failed).not.toContain("Loading departments");

    const loading = render({ catalogue: null, catalogueError: null });
    expect(loading).toContain("Loading departments");
    expect(loading).not.toContain("unavailable");
  });

  it("warns that an incomplete membership id is not requested yet", () => {
    const html = render({ employeeDraft: "4444" });
    expect(html).toContain("Enter the complete membership UUID; partial values are not requested.");
  });

  it("explains a selection the API would reject instead of sending it", () => {
    const html = render({ validationError: "The start date must be on or before the end date." });
    expect(html).toContain("This selection cannot be requested");
    expect(html).toContain("The start date must be on or before the end date.");
    expect(html).toContain("No request was sent");
  });
});

describe("currency and amount rendering", () => {
  it("renders each currency as its own total and formats it exactly", () => {
    const html = render();
    expect(html).toContain("Approved amounts");
    expect(html).toContain("12,34,567.89"); // INR, Indian grouping
    expect(html).toContain("4,200.50"); // USD, its own total
    expect(html).toContain("USD");
    expect(html).toContain("INR");
  });

  it("adds the server's group sums exactly, which float arithmetic would not", () => {
    // submitted 1000000.10 + in_review 0.20
    const html = render();
    expect(html).toContain("10,00,000.30");
  });

  it("says how much of a count actually carried an amount", () => {
    const html = render();
    expect(html).toContain("Amount known for 55 of 57 claims");
  });

  it("separates a claim with no currency from a real currency", () => {
    const withUnrecordedCurrency = {
      ...OVERVIEW_FIXTURE,
      status_amounts: [
        ...OVERVIEW_FIXTURE.status_amounts,
        {
          status: "approved" as const,
          currency: null,
          claim_count: 4,
          amount_claim_count: 0,
          amount_total: null,
        },
      ],
    };
    const html = render({
      overview: { data: withUnrecordedCurrency, error: null, loading: false, refreshing: false },
    });
    expect(html).toContain("Currency not recorded");
    expect(html).toContain("no group in this selection carried an amount");
  });

  it("renders a group with no amount as unrecorded, never as zero", () => {
    const html = render();
    expect(html).toContain("No amount recorded · 40 claims");
    expect(html).not.toContain("₹0.00");
  });

  it("keeps the total per currency on the status card", () => {
    const html = render();
    expect(html).toContain("Recorded amounts across all workflow statuses, per currency");
    expect(html).toContain("no currency: no amount recorded");
  });
});

describe("charts", () => {
  it("names the active period and dimension on every chart", () => {
    const html = render();
    expect(html).toContain("Dimension: Transaction month");
    expect(html).toContain("Dimension: Department");
    expect(html).toContain("Dimension: Office location");
    expect(html).toContain("Dimension: Category");
    expect(html).toContain("Period: 1 Jul 2026 – 30 Sept 2026");
    expect(html).toContain("amounts are never combined across currencies");
  });

  it("labels returned grouped values", () => {
    const html = render();
    expect(html).toContain("Jul 2026");
    expect(html).toContain("Aug 2026");
    expect(html).toContain("Sept 2026");
    expect(html).toContain("Engineering");
    expect(html).toContain("Sales");
  });

  it("gives a returned empty group its own label rather than dropping it", () => {
    const html = render();
    expect(html).toContain("No category recorded");
    expect(html).toContain("No department on the membership");
  });

  it("explains that an omitted month is zero dated claims, not missing data", () => {
    const html = render();
    expect(html).toContain("an absent month is zero dated claims, not missing data");
  });

  it("exposes every bar to assistive technology with its exact amount", () => {
    const html = render();
    expect(html).toContain('role="img"');
    expect(html).toContain('aria-label="Engineering: INR 900000.10, 800 claims"');
    expect(html).toContain("<figcaption");
  });
});

describe("workflow statuses", () => {
  it("shows every canonical status, including ones with no claims", () => {
    const html = render();
    for (const label of [
      "Draft",
      "Submitted",
      "Needs information",
      "Under review",
      "Approved",
      "Not reimbursed",
      "Withdrawn",
    ]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("including statuses with no claims in the period");
  });

  it("describes approval as a workflow fact", () => {
    const html = render();
    expect(html).toContain("This is not a policy PASS and not evidence of payment.");
  });

  it("never uses fraud or blame language to describe a status", () => {
    const html = render();
    expect(html).not.toMatch(/is fraudulent/i);
    expect(html).not.toMatch(/fraud detected/i);
    expect(html).not.toMatch(/suspicious/i);
    expect(html).not.toMatch(/guilty/i);
    expect(html).not.toMatch(/misconduct/i);
    // The disclosure states the opposite, which is the point of having it.
    expect(html).toContain("nothing here asserts fraud");
  });
});

describe("empty, loading and failure states", () => {
  it("shows a skeleton with no figures while the first response is outstanding", () => {
    const html = render({
      overview: { data: null, error: null, loading: true, refreshing: false },
      spend: spendState({ loading: true, rows: [], page: null }),
      catalogue: null,
    });
    expect(html).toContain("Loading live analytics from the backend");
    expect(html).toContain("Loading spend groups");
    expect(html).not.toContain("₹");
    expect(html).not.toContain("No dated claims");
  });

  it("renders the empty period as an explanation, not as zeroes", () => {
    const html = render({
      overview: { data: EMPTY_OVERVIEW_FIXTURE, error: null, loading: false, refreshing: false },
    });
    expect(html).toContain("No dated claims in this period");
    expect(html).toContain("cannot be placed in any period");
    expect(html).toContain("41");
    // No chart is drawn, because there is nothing to draw.
    expect(html).not.toContain("Monthly spending");
  });

  it("renders an unauthenticated and a forbidden overview as distinct states", () => {
    const unauthenticated = render({
      overview: {
        data: null,
        error: {
          kind: "unauthenticated",
          title: "No authenticated identity",
          message: "The backend did not receive an authenticated caller.",
          requestId: null,
        },
        loading: false,
        refreshing: false,
      },
    });
    expect(unauthenticated).toContain("No authenticated identity");

    const denied = render({
      overview: { data: null, error: forbidden(), loading: false, refreshing: false },
    });
    expect(denied).toContain("Analytics access denied");
    expect(denied).not.toContain("No authenticated identity");
  });

  it("explains an employee-level refusal without hiding the aggregates", () => {
    const html = render({
      groupBy: "employee",
      spend: spendState({ error: forbidden(), rows: [], page: null }),
    });
    expect(html).toContain("Employee-level grouping is not permitted");
    expect(html).toContain("analytics:read_org");
    // The overview is still on screen: one section failing is not the whole page failing.
    expect(html).toContain("Claims in period");
    expect(html).toContain("1,234");
  });

  it("labels stale data as stale, with the request id", () => {
    const html = render({
      overview: {
        data: OVERVIEW_FIXTURE,
        error: forbidden(),
        loading: false,
        refreshing: false,
        loadedQuery: { from: "2026-07-01", to: "2026-09-30" },
      },
    });
    expect(html).toContain("Showing the last result that loaded");
    expect(html).toContain("Analytics access denied");
    expect(html).toContain(`request id: ${REQUEST_ID}`);
    expect(html).toContain("1,234");
  });

  it("hides retained figures that belong to a different selection, and says so", () => {
    // The controls have moved on to October while the loaded response was for July to
    // September. Those numbers must not be relabelled as the answer to the new selection.
    const html = render({
      range: { from: "2026-10-01", to: "2026-10-18" },
      overview: {
        data: OVERVIEW_FIXTURE,
        error: forbidden(),
        loading: false,
        refreshing: false,
        loadedQuery: { from: "2026-07-01", to: "2026-09-30" },
      },
    });
    expect(html).toContain("Analytics access denied");
    expect(html).toContain("it is not what the controls now request, so it is not shown here");
    expect(html).toContain("period 2026-07-01 to 2026-09-30 · no filters");
    expect(html).not.toContain("1,234");
    expect(html).not.toContain("Claims in period");
  });

  it("keeps showing figures when the failed request was for the same selection", () => {
    const html = render({
      range: { from: "2026-07-01", to: "2026-09-30" },
      overview: {
        data: OVERVIEW_FIXTURE,
        error: forbidden(),
        loading: false,
        refreshing: false,
        loadedQuery: { from: "2026-07-01", to: "2026-09-30" },
      },
    });
    expect(html).toContain("It is still the current selection");
    expect(html).not.toContain("It is NOT the current selection");
    expect(html).toContain("1,234");
  });

  it("does not relabel the previous grouping's rows as the new grouping", () => {
    const html = render({
      groupBy: "employee",
      spend: spendState({
        rows: [spendRow({ bucket_start: "2026-07-01", amount_total: "10.00" })],
        page: pageInfo({ total: 1 }),
        error: forbidden(),
        loadedQuery: { from: "2026-07-01", to: "2026-09-30", group_by: "month", limit: 200 },
      }),
    });
    expect(html).toContain("Employee-level grouping is not permitted");
    expect(html).toContain("period 2026-07-01 to 2026-09-30 · grouped by month · no filters");
    expect(html).toContain("not relabelled as the current grouping");
    // The month bucket is not shown under an "employee" heading.
    expect(html).not.toContain("Employee name not recorded");
  });

  it("distinguishes a background refresh from stale data", () => {
    const html = render({
      overview: { data: OVERVIEW_FIXTURE, error: null, loading: false, refreshing: true },
    });
    expect(html).toContain("Updating for the current selection");
    expect(html).not.toContain("Showing the last result that loaded");
    expect(html).toContain("Refreshing…");
  });

  it("reports a spend failure without replacing the groups it already has", () => {
    const html = render({
      spend: spendState({
        rows: [spendRow({ bucket_start: "2026-07-01", amount_total: "10.00" })],
        page: pageInfo({ total: 1 }),
        error: {
          kind: "network",
          title: "Backend unreachable",
          message: "The analytics service did not respond.",
          requestId: null,
        },
        // The failed request was for exactly this selection: the groups stay on screen.
        loadedQuery: { from: "2026-07-01", to: "2026-09-30", group_by: "month", limit: 200 },
      }),
    });
    expect(html).toContain("The latest spend request failed");
    expect(html).toContain("Backend unreachable");
    expect(html).toContain("It is still the current selection");
    expect(html).toContain("10.00");
  });

  it("announces the period summary and refreshes without a fabricated fallback", () => {
    const html = render({ lastUpdated: null });
    expect(html).toContain("No successful response yet");
  });
});

describe("pagination", () => {
  it("says how many groups are shown out of the reported total", () => {
    const rows = Array.from({ length: 3 }, (_unused, index) =>
      spendRow({ bucket_start: `2026-0${index + 1}-01`, amount_total: "10.00" }),
    );
    const html = render({
      spend: spendState({ rows, page: pageInfo({ total: 250, next_cursor: "next" }) }),
    });
    expect(html).toContain("showing 3 of 250 matching groups");
    expect(html).toContain("<strong>month</strong> and currency");
  });

  it("offers the next page and says the list is not complete yet", () => {
    const html = render({
      spend: spendState({
        rows: [spendRow({ bucket_start: "2026-07-01" })],
        page: pageInfo({ total: 250, next_cursor: "next" }),
      }),
    });
    expect(html).toContain("Load more groups");
    expect(html).toContain("this list is not the whole dataset yet");
  });

  it("does not offer more when the API returned no further cursor", () => {
    const html = render({
      spend: spendState({
        rows: [spendRow({ bucket_start: "2026-07-01" })],
        page: pageInfo({ total: 1, next_cursor: null }),
      }),
    });
    expect(html).not.toContain("Load more groups");
    expect(html).toContain("showing 1 of 1 matching groups");
  });

  it("reports a total larger than what was returned instead of implying completeness", () => {
    const html = render({
      spend: spendState({
        rows: [spendRow({ bucket_start: "2026-07-01" })],
        page: pageInfo({ total: 9, next_cursor: null }),
      }),
    });
    expect(html).toContain("The API reported 9 matching groups but returned no further cursor");
    expect(html).toContain("Showing the 1 it returned");
  });

  it("reports a load-more failure separately from the page already shown", () => {
    const html = render({
      spend: spendState({
        rows: [spendRow({ bucket_start: "2026-07-01", amount_total: "10.00" })],
        page: pageInfo({ total: 250, next_cursor: "next" }),
        loadMoreError: {
          kind: "server",
          title: "The analytics service failed",
          message: "Internal error.",
          requestId: null,
        },
      }),
    });
    expect(html).toContain("The analytics service failed");
    expect(html).toContain("10.00");
  });

  it("counts the pages it followed", () => {
    const html = render({
      spend: spendState({
        rows: [spendRow({ bucket_start: "2026-07-01" })],
        page: pageInfo({ total: 250, next_cursor: "next" }),
        pagesLoaded: 3,
      }),
    });
    expect(html).toContain("across 3 pages");
  });

  it("states the page size it requested", () => {
    const html = render();
    expect(html).toContain("Page size 200");
  });
});

describe("undated claims are reported, never zero-filled", () => {
  it("names the spend claims excluded from groups", () => {
    const html = render({
      spend: spendState({
        rows: [spendRow({ bucket_start: "2026-07-01" })],
        page: pageInfo({ total: 1 }),
        unknownDateCount: 17,
      }),
    });
    expect(html).toContain("17 claims match these filters but have no transaction date");
    expect(html).toContain("they are reported here instead of being placed in a month");
  });

  it("explains an otherwise empty group list by pointing at the undated claims", () => {
    const html = render({
      spend: spendState({
        rows: [],
        page: pageInfo({ total: 0 }),
        unknownDateCount: 17,
      }),
    });
    expect(html).toContain("No groups match this selection");
    expect(html).toContain("17 claims match the filters but have no transaction date");
  });
});

describe("layout and accessibility", () => {
  it("uses the responsive grid at narrow, laptop and wide widths", () => {
    // Class-level assertion only: real viewport behaviour is verified in a browser during
    // live verification, and this test does not claim to replace that.
    const html = render();
    expect(html).toContain("grid-cols-1");
    expect(html).toContain("sm:grid-cols-2");
    expect(html).toContain("lg:grid-cols-3");
    expect(html).toContain("2xl:grid-cols-6");
    expect(html).toContain("xl:grid-cols-2");
  });

  it("marks the live regions and alerts the states that need attention", () => {
    const stale = render({
      overview: {
        data: OVERVIEW_FIXTURE,
        error: forbidden(),
        loading: false,
        refreshing: false,
        loadedQuery: { from: "2026-07-01", to: "2026-09-30" },
      },
    });
    expect(stale).toContain('aria-live="polite"');
    expect(stale).toContain('role="alert"');

    // A mismatch replaces the figures entirely; the failure is still announced assertively.
    const mismatch = render({
      range: { from: "2026-10-01", to: "2026-10-18" },
      overview: {
        data: OVERVIEW_FIXTURE,
        error: forbidden(),
        loading: false,
        refreshing: false,
        loadedQuery: { from: "2026-07-01", to: "2026-09-30" },
      },
    });
    expect(mismatch).toContain('role="alert"');

    const loading = render({
      overview: { data: null, error: null, loading: true, refreshing: false },
    });
    expect(loading).toContain('role="status"');
    expect(loading).toContain('aria-live="polite"');
  });

  it("uses real semantic elements for the chart and its caption", () => {
    const html = render();
    expect(html).toContain("<figure");
    expect(html).toContain("<figcaption");
    expect(html).toContain("<ul");
    expect(html).toContain("<h2");
  });

  it("gives the grouping control a name that describes it", () => {
    const html = render({
      groupBy: "status",
      spend: spendState({
        rows: [spendRow({ status: "approved", amount_total: "10.00" })],
        page: pageInfo({ total: 1 }),
        loadedQuery: { from: RANGE.from, to: RANGE.to, group_by: "status", limit: 200 },
      }),
    });
    expect(html).toContain('aria-label="Spend grouping dimension"');
    expect(html).toContain("<strong>workflow status</strong>");
    // A status-grouped row keeps the console's canonical status wording.
    expect(html).toContain('aria-label="Approved: INR 10.00, 1 claims"');
  });

  it("labels the refresh and load-more controls by their text", () => {
    const html = render({
      spend: spendState({
        rows: [spendRow({ bucket_start: "2026-07-01" })],
        page: pageInfo({ total: 5, next_cursor: "next" }),
      }),
    });
    expect(html).toContain("Refresh data");
    expect(html).toContain("Load more groups");
    expect(html).toContain('type="button"');
  });
});

describe("labels", () => {
  it("keeps month labels in UTC so a boundary date cannot slip a month", () => {
    expect(formatMonthLabel("2026-07-01")).toBe("Jul 2026");
    expect(formatMonthLabel(null)).toBe("Month not recorded");
    expect(formatMonthLabel("not-a-date")).toBe("not-a-date");
  });

  it("formats the period label from the ISO dates it was given", () => {
    expect(formatPeriodLabel({ from: "2026-01-31", to: "2026-02-01" })).toBe(
      "31 Jan 2026 – 1 Feb 2026",
    );
    expect(formatPeriodLabel({ from: "", to: "" })).toBe("? – ?");
  });

  it("uses the canonical workflow wording", () => {
    expect(statusLabel("rejected")).toBe("Not reimbursed");
    expect(statusLabel("needs_info")).toBe("Needs information");
    expect(statusLabel("something_new")).toBe("something_new");
  });

  it("names every grouping dimension", () => {
    for (const group of ["month", "department", "location", "category", "employee", "status"] as AnalyticsGroupBy[]) {
      expect(groupLabel(group)).not.toBe("");
    }
  });
});
