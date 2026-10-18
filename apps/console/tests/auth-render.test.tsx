/**
 * 401, 403 and transport failures render as three different screens.
 *
 * Rendered with `react-dom/server`, so the assertion is on the markup a user would receive,
 * not on a mock. The important property is that a 403 never reads as a sign-in problem: the
 * copy must not suggest re-authenticating, because that would hide an authorization refusal.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  BackendUnavailableState,
  ForbiddenState,
  UnauthenticatedState,
} from "../src/components/AuthStates";

const REQUEST_ID = "e2c6b1f4-0000-4000-8000-000000000000";

function render(node: Parameters<typeof renderToStaticMarkup>[0]): string {
  return renderToStaticMarkup(node).replace(/[\u00a0\u202f]/g, " ");
}

describe("401 renders as an unauthenticated state", () => {
  const html = render(<UnauthenticatedState />);

  it("asks the visitor to sign in and links to the sign-in route", () => {
    expect(html).toMatch(/Sign in to continue/);
    expect(html).toContain('href="/login"');
  });

  it("does not claim an authorization problem", () => {
    expect(html).not.toMatch(/do not have access/i);
    expect(html).not.toMatch(/membership/i);
  });

  it("explains an expired session differently from a missing one", () => {
    const expired = render(<UnauthenticatedState expired />);
    expect(expired).toMatch(/session is no longer valid/i);
    expect(expired).not.toBe(html);
  });

  it("sends a demo visitor to the actor field, not to a sign-in that cannot work", () => {
    const demo = render(<UnauthenticatedState demo />);
    expect(demo).toMatch(/X-Demo-Actor-Id/);
    expect(demo).toMatch(/not a sign-in/i);
    // No loop: there is no sign-in route to complete in demo mode.
    expect(demo).not.toContain('href="/login"');
    expect(demo).not.toMatch(/Sign in to continue/i);
  });
});

describe("403 renders as a forbidden state", () => {
  const html = render(<ForbiddenState requestId={REQUEST_ID} />);

  it("states that the identity was accepted but is not permitted", () => {
    expect(html).toMatch(/do not have access to the console/i);
    expect(html).toMatch(/membership/i);
    expect(html).toContain(REQUEST_ID);
  });

  it("does not advise signing in again", () => {
    // The whole point of distinguishing 403: re-authenticating cannot change a membership,
    // so offering it would send the user round a loop and hide the refusal.
    expect(html).not.toMatch(/sign in/i);
    expect(html).not.toMatch(/log in/i);
    expect(html).not.toMatch(/href="\/login"/);
  });

  it("offers no retry control", () => {
    expect(html).not.toMatch(/<button/i);
  });
});

describe("a transport or server failure is its own state", () => {
  it("shows the error and says no figures are substituted", () => {
    const html = render(
      <BackendUnavailableState
        title="Backend unreachable"
        message="The console could not reach the backend."
        requestId={REQUEST_ID}
      />,
    );
    expect(html).toContain("Backend unreachable");
    expect(html).toContain("The console could not reach the backend.");
    expect(html).toMatch(/no figures are shown/i);
    expect(html).toContain(REQUEST_ID);
    // Not confusable with either auth state.
    expect(html).not.toMatch(/sign in/i);
    expect(html).not.toMatch(/do not have access/i);
  });
});
