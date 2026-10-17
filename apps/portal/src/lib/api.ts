/**
 * Employee portal API access.
 *
 * The portal talks to the backend and to nothing else: no database URL, no service-role
 * key, no extraction credential. Everything it can see is what the backend returns for the
 * current actor.
 *
 * ---------------------------------------------------------------------------
 * OWNERSHIP IS ENFORCED BY THE BACKEND, NOT BY THIS APPLICATION
 *
 * There is no "my expenses" filter applied here, and none should be added. The backend
 * scopes every claim, receipt and audit read to the authenticated actor, and returns the
 * same response for a record that does not exist as for one the caller may not see - so a
 * claim's existence is never disclosed to someone who should not know it.
 *
 * Client-side filtering is not a security control: anyone can call the API directly. If
 * this application ever appears to be hiding data by filtering, that is a bug, not a
 * control.
 * ---------------------------------------------------------------------------
 */

import { createApiClient, type ApiClientOptions } from "@proofline/api-client";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const DEMO_MODE_ENABLED = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export const DEMO_ACTOR_STORAGE_KEY = "proofline.portal.demoActorId";

export function readDemoActorId(): string | null {
  if (!DEMO_MODE_ENABLED || typeof window === "undefined") return null;
  return window.localStorage.getItem(DEMO_ACTOR_STORAGE_KEY);
}

export function writeDemoActorId(actorId: string | null): void {
  if (typeof window === "undefined") return;
  if (actorId) {
    window.localStorage.setItem(DEMO_ACTOR_STORAGE_KEY, actorId);
  } else {
    window.localStorage.removeItem(DEMO_ACTOR_STORAGE_KEY);
  }
  window.location.reload();
}

export function portalApiOptions(
  overrides: Partial<ApiClientOptions> = {},
): ApiClientOptions {
  return {
    baseUrl: API_BASE_URL,
    getDemoActorId: readDemoActorId,
    // Replacing demo mode with real authentication is a change to this one function.
    getToken: () => null,
    ...overrides,
  };
}

export function createPortalApi(overrides: Partial<ApiClientOptions> = {}) {
  return createApiClient(portalApiOptions(overrides));
}
