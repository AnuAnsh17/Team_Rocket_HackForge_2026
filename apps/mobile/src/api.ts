/**
 * API access for the employee app.
 *
 * The app talks to the backend and to nothing else. It holds no database URL, no
 * service-role key and no extraction credential, because an app bundle is trivially
 * extractable and anything in it is public.
 *
 * ---------------------------------------------------------------------------
 * OWNERSHIP IS ENFORCED BY THE BACKEND
 *
 * The app does not filter claims by employee, and must never start. The backend scopes
 * every claim, receipt and audit read to the authenticated actor, and returns the same
 * response for a record that does not exist as for one the caller may not see, so another
 * employee's claim is never revealed. Client-side filtering is not a security control.
 * ---------------------------------------------------------------------------
 */

import Constants from "expo-constants";

import { createApiClient, type ApiClientOptions, type ProoflineClient } from "@proofline/api-client";

interface ExtraConfig {
  apiBaseUrl?: string;
}

const extra = (Constants.expoConfig?.extra ?? {}) as ExtraConfig;

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? extra.apiBaseUrl ?? "http://localhost:8000/api/v1";

export const DEMO_MODE_ENABLED = process.env.EXPO_PUBLIC_DEMO_MODE !== "false";

/**
 * The demo actor id.
 *
 * Held in memory only for the scaffold: a real build will read a token from secure
 * storage. Demo mode identifies a USER - the backend resolves roles and scope itself - so
 * no role is ever sent, and none can be.
 */
let demoActorId: string | null = null;

export function setDemoActorId(actorId: string | null): void {
  demoActorId = actorId;
}

export function getDemoActorId(): string | null {
  return DEMO_MODE_ENABLED ? demoActorId : null;
}

export function mobileApiOptions(
  overrides: Partial<ApiClientOptions> = {},
): ApiClientOptions {
  return {
    // OpenAPI paths already include /api/v1, so openapi-fetch needs only the origin.
    baseUrl: API_BASE_URL.replace(/\/api\/v1\/?$/, ""),
    getDemoActorId,
    // Replacing demo mode with real authentication is a change to this one function.
    getToken: () => null,
    ...overrides,
  };
}

export function createMobileApi(overrides: Partial<ApiClientOptions> = {}): ProoflineClient {
  return createApiClient(mobileApiOptions(overrides));
}

/**
 * Plain-language translation of a transport failure.
 *
 * "Cannot reach the server" and "the server refused this" are different problems for the
 * person holding the phone, and only one of them is worth retrying once they have signal.
 */
export function describeConnectionProblem(error: unknown): string {
  if (error instanceof Error && error.message.includes("Network request failed")) {
    return "No connection to Proofline. Your receipt is still on this device - try again once you have signal.";
  }
  return "Something went wrong talking to Proofline. Nothing has been submitted.";
}
