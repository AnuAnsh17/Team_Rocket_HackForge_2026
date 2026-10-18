"use client";

/**
 * The backend-resolved identity, loaded once per session.
 *
 * `GET /api/v1/me` is the smallest endpoint that proves the whole authorization path: it
 * verifies the credential, resolves the subject to a provisioned user, loads an active
 * membership from the database and answers 401/403 itself. That makes it the honest place
 * for the console to learn who it is talking to, and the reason the console never derives
 * an identity from a decoded token.
 *
 * Its failure modes are the console's failure modes, which is why they are captured here
 * rather than per page:
 *   401 -> no valid identity        -> return to sign-in
 *   403 -> valid identity, no access -> a forbidden state that must not be retried
 *   5xx / network                    -> an error, never a zeroed dashboard
 */

import { unwrap, type Membership } from "@proofline/api-client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { useConsoleAuth } from "@/components/AuthProvider";
import { createConsoleApi } from "@/lib/api";
import { createRequestGate, describeError, type AnalyticsError } from "@/lib/analytics";
import { identityKeyFromMembership } from "@/lib/auth/session";

/** One client for the whole shell. The token is read per request, not captured here. */
const consoleApi = createConsoleApi();

export interface IdentityContextValue {
  /** True until the first identity response has been applied. */
  loading: boolean;
  membership: Membership | null;
  error: AnalyticsError | null;
  /** Stable key of the resolved identity; keys the console content. */
  identityKey: string;
  refresh: () => void;
}

const IdentityContext = createContext<IdentityContextValue | null>(null);

export function useBackendIdentity(): IdentityContextValue {
  const value = useContext(IdentityContext);
  if (!value) throw new Error("useBackendIdentity must be used inside <IdentityProvider>.");
  return value;
}

export function IdentityProvider({ children }: { children: ReactNode }) {
  const auth = useConsoleAuth();
  const [membership, setMembership] = useState<Membership | null>(null);
  const [error, setError] = useState<AnalyticsError | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);
  const gate = useRef(createRequestGate());

  const ready = auth.status === "authenticated" || auth.status === "demo";

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  useEffect(() => {
    if (!ready) {
      // No session to resolve yet (still restoring) or none at all.
      setLoading(auth.status === "loading");
      return;
    }

    const token = gate.current.begin();
    setLoading(true);
    setError(null);

    void unwrap(consoleApi.GET("/api/v1/me"))
      .then((resolved) => {
        if (!gate.current.isCurrent(token)) return;
        setMembership(resolved);
        setError(null);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!gate.current.isCurrent(token)) return;
        // Drop the identity on failure: keeping a previous account's membership visible
        // while its successor is failing is exactly the cross-account leak to avoid.
        setMembership(null);
        setError(describeError(cause));
        setLoading(false);
      });
    // `auth.identityKey` is a dependency on purpose: when the account changes the identity
    // is re-resolved, so a stale membership cannot survive an account switch.
  }, [ready, auth.status, auth.identityKey, reloadToken]);

  const value = useMemo<IdentityContextValue>(
    () => ({
      loading,
      membership,
      error,
      identityKey: identityKeyFromMembership(membership),
      refresh,
    }),
    [loading, membership, error, refresh],
  );

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}
