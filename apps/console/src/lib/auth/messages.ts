/**
 * Sign-in error wording, and the redaction that keeps a credential out of it.
 *
 * Two rules drive this file:
 *
 * 1. A user is told what happened and what to do, in the product's own words - never the
 *    identity provider's raw payload, which can carry a token, an internal host name or a
 *    database message.
 * 2. Nothing that reaches a message, a log line or a thrown error may contain an access
 *    token, a refresh token or a password. {@link redactSensitive} is applied to the
 *    fallback path so an unexpected provider message cannot leak one either.
 */

/** Error shape this module understands, from a Supabase error or a thrown value. */
export interface AuthErrorLike {
  message?: string | null;
  status?: number | null;
  code?: string | null;
  name?: string | null;
}

/**
 * A JWT-looking string (`header.payload.signature`, base64url) and the credential words.
 *
 * Deliberately broad: it is better to over-redact a message than to print a token.
 */
const SENSITIVE_PATTERNS: RegExp[] = [
  // A JWT: three base64url segments. The signature is the part that must never be shown.
  /eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}/g,
  /\b(bearer)\s+[A-Za-z0-9._~+/-]+=*/gi,
  /\b(access_token|refresh_token|id_token|password|apikey|api_key|secret|service_role)\b\s*[:=]?\s*[^\s,;"']*/gi,
];

/** Replace anything that looks like a credential with a fixed marker. */
export function redactSensitive(text: string): string {
  let output = text;
  for (const pattern of SENSITIVE_PATTERNS) {
    output = output.replace(pattern, (match) => {
      // Keep a bare `password`/`token` word if it had no value attached; only blank values.
      const hasValue = /[:=]\s*\S/.test(match) || match.includes(" ") || match.startsWith("eyJ");
      return hasValue ? "[redacted]" : match;
    });
  }
  return output;
}

function asAuthError(error: unknown): AuthErrorLike {
  if (typeof error === "string") return { message: error };
  if (typeof error !== "object" || error === null) return {};
  const candidate = error as Record<string, unknown>;
  return {
    message: typeof candidate.message === "string" ? candidate.message : null,
    status: typeof candidate.status === "number" ? candidate.status : null,
    code: typeof candidate.code === "string" ? candidate.code : null,
    name: typeof candidate.name === "string" ? candidate.name : null,
  };
}

/**
 * Turn a failed sign-in into one sentence a person can act on.
 *
 * The provider's message is inspected only to choose a branch; it is never echoed, so no
 * provider payload - and therefore no token or password - can reach the screen or a log.
 */
export function mapSignInError(error: unknown): string {
  const { message, status, code, name } = asAuthError(error);
  const haystack = `${message ?? ""} ${code ?? ""}`.toLowerCase();

  // A transport failure: the browser never reached the auth service.
  if (
    name === "AuthRetryableFetchError" ||
    /fetch failed|failed to fetch|networkerror|network request failed|load failed|econnrefused|enotfound|timed? ?out/.test(
      haystack,
    )
  ) {
    return "The sign-in service could not be reached. Check your connection and try again.";
  }

  if (status === 429 || /rate limit|too many|over_email_send_rate_limit/.test(haystack)) {
    return "Too many sign-in attempts. Wait a moment and try again.";
  }

  if (/invalid login credentials|invalid_grant|invalid credentials/.test(haystack)) {
    return "That email address and password combination was not accepted.";
  }

  if (/email not confirmed|email_not_confirmed/.test(haystack)) {
    return "This account's email address has not been confirmed yet. Confirm it, then sign in.";
  }

  if (/password should be at least|weak password|password.*too short/.test(haystack)) {
    return "That password does not meet the minimum length. Use a longer password.";
  }

  if (/invalid email|email_address_invalid|unable to validate email/.test(haystack)) {
    return "That does not look like an email address. Check it and try again.";
  }

  if (status === 400 || status === 401 || status === 403) {
    return "Sign-in was refused. Check the email address and password, then try again.";
  }

  // Anything unrecognized: state that it failed and attach nothing from the provider.
  return "Sign-in failed. Check the email address and password, then try again.";
}

/**
 * A safe, non-sensitive description of a failed sign-in for a diagnostic line.
 *
 * Returns only a status/code/name triple - never the provider message, which is where a
 * credential could appear. Callers may log this freely.
 */
export function describeSignInFailure(error: unknown): string {
  const { status, code, name } = asAuthError(error);
  const parts = [
    `status=${status ?? "unknown"}`,
    `code=${redactSensitive(code ?? "unknown")}`,
    `name=${name ?? "unknown"}`,
  ];
  return parts.join(" ");
}
