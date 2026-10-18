"use client";

/**
 * Renders the console content, or the one honest state that replaces it.
 *
 * A page is only shown once the backend has confirmed an identity. Until then, and when the
 * identity request fails, the user sees a screen that names what happened - never a
 * partially-loaded console, never a page of zeros.
 */

import type { ReactNode } from "react";

import { UnauthenticatedState, ForbiddenState, BackendUnavailableState } from "@/components/AuthStates";
import { useConsoleAuth } from "@/components/AuthProvider";
import { useBackendIdentity } from "@/components/IdentityProvider";
import { LoadingState } from "@/components/ui";

export function IdentityGate({ children }: { children: ReactNode }) {
  const auth = useConsoleAuth();
  const { loading, membership, error } = useBackendIdentity();

  if (auth.status === "loading") {
    return <LoadingState label="Restoring your session" />;
  }

  if (auth.status === "anonymous") {
    // No session at all. The proxy normally redirects before this renders; this is the
    // in-page fallback when a session is lost while the console is open.
    return <UnauthenticatedState expired={Boolean(error)} demo={auth.mode === "demo"} />;
  }

  if (loading && !membership) {
    return <LoadingState label="Resolving your identity with the backend" />;
  }

  if (error) {
    if (error.kind === "unauthenticated") {
      // 401: an expired or rejected token, or no demo actor id. Return to sign-in; do not
      // retry.
      return <UnauthenticatedState expired demo={auth.mode === "demo"} />;
    }
    if (error.kind === "forbidden") {
      // 403: valid identity, no authority. Never retried, never downgraded to a sign-in.
      return <ForbiddenState requestId={error.requestId} />;
    }
    // Network or server failure: say so, and show nothing in its place.
    return (
      <BackendUnavailableState
        title={error.title}
        message={error.message}
        requestId={error.requestId}
      />
    );
  }

  return <>{children}</>;
}
