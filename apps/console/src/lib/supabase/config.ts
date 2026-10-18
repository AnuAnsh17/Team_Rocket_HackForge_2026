/**
 * Client-visible Supabase configuration and the auth mode it selects.
 *
 * This module is deliberately the *only* place that reads the Supabase project
 * coordinates, and it imports nothing. That keeps two properties that matter:
 *
 * 1. It is safe in every runtime - browser bundle, server component and the edge proxy -
 *    because it touches no `window`, no `document` and no Supabase client.
 * 2. The decision "is a real Supabase project configured, and is demo identity therefore
 *    allowed?" is a pure function of the environment, so it can be tested for every
 *    combination without a live project.
 *
 * WHAT MAY APPEAR HERE: only `NEXT_PUBLIC_*` values, which are embedded in the browser
 * bundle by design. The Supabase project URL and the publishable/anon key are public.
 * A service-role key, a database URL or a JWT secret must never reach this file - or any
 * other file prefixed NEXT_PUBLIC_.
 */

/** The client-visible environment, flattened so it can be supplied by a test. */
export interface ConsoleEnv {
  supabaseUrl?: string | undefined;
  supabaseAnonKey?: string | undefined;
  /** `NEXT_PUBLIC_DEMO_MODE`; a public build flag, arriving as a string. */
  demoMode?: string | undefined;
}

export type ConsoleAuthMode = "supabase" | "demo" | "unconfigured";

export interface ConsoleAuth {
  /** A Supabase project URL *and* publishable key are both present. */
  supabaseConfigured: boolean;
  /** `NEXT_PUBLIC_DEMO_MODE === "true"`. */
  demoModeEnabled: boolean;
  /**
   * Whether the demo actor header is a usable identity path.
   *
   * True only when demo mode is switched on AND no Supabase project is configured. The
   * two are mutually exclusive on purpose: once a project exists, a real session is the
   * only way in, so the console never sends a demo actor header that the backend would
   * have to decide about.
   */
  demoModeActive: boolean;
  mode: ConsoleAuthMode;
}

/**
 * Decide the auth mode from the client-visible environment.
 *
 * Both Supabase values are required. A half-configured project (a URL with no key, or a
 * key with no URL) counts as *not configured*, so the console fails towards the demo path
 * it can actually complete rather than towards a broken sign-in.
 */
export function resolveConsoleAuth(env: ConsoleEnv): ConsoleAuth {
  const supabaseConfigured =
    (env.supabaseUrl ?? "").trim().length > 0 && (env.supabaseAnonKey ?? "").trim().length > 0;
  const demoModeEnabled = env.demoMode === "true";
  const demoModeActive = demoModeEnabled && !supabaseConfigured;

  const mode: ConsoleAuthMode = supabaseConfigured
    ? "supabase"
    : demoModeActive
      ? "demo"
      : "unconfigured";

  return { supabaseConfigured, demoModeEnabled, demoModeActive, mode };
}

/** Read the client-visible values out of a `process.env`-like record. */
export function consoleEnvFromProcess(
  env: Record<string, string | undefined> = process.env,
): ConsoleEnv {
  return {
    supabaseUrl: env.NEXT_PUBLIC_SUPABASE_URL,
    supabaseAnonKey: env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    demoMode: env.NEXT_PUBLIC_DEMO_MODE,
  };
}

/** The project URL, trimmed. Empty when unconfigured. Safe to embed in a bundle. */
export const SUPABASE_URL = (process.env.NEXT_PUBLIC_SUPABASE_URL ?? "").trim();

/**
 * The publishable/anon key, trimmed. Public by design.
 *
 * This is not a secret and is not treated as one: it authorizes nothing on its own. The
 * backend verifies tokens with the project's JWKS and loads authority from its own
 * database, so holding this key grants no capability.
 */
export const SUPABASE_ANON_KEY = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "").trim();

/**
 * The resolved mode for this build.
 *
 * These are literal `process.env.NEXT_PUBLIC_*` member expressions rather than a call to
 * `consoleEnvFromProcess`, and that is deliberate: a bundler substitutes only the
 * expressions it can see statically. Passing `process.env` as a *value* leaves the browser
 * bundle with an empty environment, so the server (where `process.env` is real) resolves the
 * demo identity gate while the hydrated page falls back to "unconfigured" and shows
 * "Sign in to continue". The split is invisible in `next dev`, which injects the public
 * variables at runtime for the client, and appears only in a production build - which is
 * precisely the build an image ships.
 */
export const CONSOLE_AUTH: ConsoleAuth = resolveConsoleAuth({
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL,
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  demoMode: process.env.NEXT_PUBLIC_DEMO_MODE,
});
