/**
 * The three ways a console request can fail to show data, as distinct screens.
 *
 * They are separate components because conflating them is how a product lies. A 401 means
 * "we do not know who you are" and is fixed by signing in. A 403 means "we know who you
 * are and you are not permitted" and is NOT fixed by signing in again - telling someone to
 * re-authenticate hides an authorization refusal and sends them round a loop. A network
 * or server failure is neither, and must never be rendered as zeros.
 *
 * Plain anchors rather than `next/link` are used so these render outside the App Router
 * (they are exercised by a static-render test), and so a failure state never depends on
 * client-side routing being healthy.
 */

import type { ReactNode } from "react";

function AuthStateCard({
  title,
  message,
  children,
}: {
  title: string;
  message: string;
  children?: ReactNode;
}) {
  return (
    <div
      role="alert"
      data-auth-state="true"
      className="rounded-lg border border-[var(--color-severity-blocking)] bg-[var(--color-surface-raised)] p-6"
    >
      <h2 className="text-sm font-semibold text-[var(--color-text)]">{title}</h2>
      <p className="mt-2 max-w-prose text-sm text-[var(--color-text-muted)]">{message}</p>
      {children}
    </div>
  );
}

/** 401: there is no valid identity. The only fix is to sign in. */
export function UnauthenticatedState({
  expired = false,
  demo = false,
}: {
  /** True when a session existed and was rejected - the wording differs by a little. */
  expired?: boolean;
  /**
   * True in local demo mode, where there is no sign-in to send the visitor to.
   *
   * Sending a demo visitor to `/login` would be a loop: that route exists but has no
   * identity provider behind it. The honest instruction is to set a demo actor id.
   */
  demo?: boolean;
}) {
  if (demo) {
    return (
      <AuthStateCard
        title="No actor is selected"
        message={
          "Demo mode identifies an actor by id. Enter the id of a seeded user in the console " +
          "header (X-Demo-Actor-Id) to load data. This is a development affordance, not a " +
          "sign-in."
        }
      >
        <p className="mt-4 text-xs text-[var(--color-text-muted)]">
          The backend must be running with demo mode enabled for the id to resolve.
        </p>
      </AuthStateCard>
    );
  }

  return (
    <AuthStateCard
      title="Sign in to continue"
      message={
        expired
          ? "Your session is no longer valid, so the console sent you back here. Sign in again to continue."
          : "The console needs a signed-in identity before it can load anything from the backend."
      }
    >
      <p className="mt-4">
        <a
          href="/login"
          className="inline-block rounded border border-[var(--color-border-strong)] px-3 py-1.5 text-sm font-medium text-[var(--color-text)]"
        >
          Go to sign in
        </a>
      </p>
    </AuthStateCard>
  );
}

/**
 * 403: the identity is valid but not permitted.
 *
 * Deliberately offers no retry and no "sign in again": neither would change a membership.
 */
export function ForbiddenState({ requestId }: { requestId?: string | null }) {
  return (
    <AuthStateCard
      title="You do not have access to the console"
      message={
        "Your sign-in was accepted and the backend recognised you, but it found no active " +
        "membership with permission to read this data. Access is granted by an " +
        "organization administrator adding a membership and a role - signing in again will " +
        "not change the answer, and this console will not retry the request."
      }
    >
      {requestId && (
        <p className="mt-3 font-mono text-xs text-[var(--color-text-muted)]">
          request id: {requestId}
        </p>
      )}
    </AuthStateCard>
  );
}

/** A transport or server failure: the request never produced an answer. */
export function BackendUnavailableState({
  title,
  message,
  requestId,
}: {
  title: string;
  message: string;
  requestId?: string | null;
}) {
  return (
    <AuthStateCard title={title} message={message}>
      <p className="mt-3 max-w-prose text-xs text-[var(--color-text-muted)]">
        No figures are shown because the backend did not answer. Nothing here is a zero or a
        substituted value.
      </p>
      {requestId && (
        <p className="mt-2 font-mono text-xs text-[var(--color-text-muted)]">
          request id: {requestId}
        </p>
      )}
    </AuthStateCard>
  );
}
