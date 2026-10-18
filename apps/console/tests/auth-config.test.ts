/**
 * Auth-mode resolution.
 *
 * The rule under test: demo identity is available ONLY when no Supabase project is
 * configured. This is where "the demo header is never sent once Supabase is configured" is
 * actually decided, so it is tested for every combination rather than assumed.
 */

import { describe, expect, it } from "vitest";

import { consoleEnvFromProcess, resolveConsoleAuth } from "../src/lib/supabase/config";

const URL_VALUE = "https://project-ref.supabase.co";
const KEY_VALUE = "public-anon-key-placeholder";

describe("resolveConsoleAuth", () => {
  it("selects supabase when a URL and a key are both present, even with demo mode on", () => {
    const auth = resolveConsoleAuth({
      supabaseUrl: URL_VALUE,
      supabaseAnonKey: KEY_VALUE,
      demoMode: "true",
    });
    expect(auth.supabaseConfigured).toBe(true);
    expect(auth.mode).toBe("supabase");
    expect(auth.demoModeEnabled).toBe(true);
    // The whole point: a configured project disables the demo identity path.
    expect(auth.demoModeActive).toBe(false);
  });

  it("selects demo only when no project is configured and the flag is on", () => {
    const auth = resolveConsoleAuth({ demoMode: "true" });
    expect(auth.supabaseConfigured).toBe(false);
    expect(auth.mode).toBe("demo");
    expect(auth.demoModeActive).toBe(true);
  });

  it("is unconfigured when nothing is set", () => {
    const auth = resolveConsoleAuth({});
    expect(auth.mode).toBe("unconfigured");
    expect(auth.supabaseConfigured).toBe(false);
    expect(auth.demoModeActive).toBe(false);
  });

  it("is unconfigured when demo mode is off and no project is set", () => {
    const auth = resolveConsoleAuth({ demoMode: "false" });
    expect(auth.mode).toBe("unconfigured");
    expect(auth.demoModeActive).toBe(false);
  });

  it("treats a half-configured project as unconfigured", () => {
    // A URL with no key, or a key with no URL, cannot complete a sign-in. Falling back to
    // whichever path can actually work is better than offering a broken one.
    for (const env of [
      { supabaseUrl: URL_VALUE, demoMode: "true" },
      { supabaseAnonKey: KEY_VALUE, demoMode: "true" },
      { supabaseUrl: "   ", supabaseAnonKey: KEY_VALUE, demoMode: "false" },
    ]) {
      const auth = resolveConsoleAuth(env);
      expect(auth.supabaseConfigured).toBe(false);
    }
  });

  it("only accepts the exact string 'true' for the demo flag", () => {
    for (const value of ["TRUE", "1", "yes", ""]) {
      expect(resolveConsoleAuth({ demoMode: value }).demoModeEnabled).toBe(false);
    }
    expect(resolveConsoleAuth({ demoMode: "true" }).demoModeEnabled).toBe(true);
  });

  it("reads the client-visible variables out of the environment", () => {
    const env = consoleEnvFromProcess({
      NEXT_PUBLIC_SUPABASE_URL: URL_VALUE,
      NEXT_PUBLIC_SUPABASE_ANON_KEY: KEY_VALUE,
      NEXT_PUBLIC_DEMO_MODE: "true",
      DATABASE_URL: "postgresql://should-not-be-read",
    });
    expect(env).toEqual({
      supabaseUrl: URL_VALUE,
      supabaseAnonKey: KEY_VALUE,
      demoMode: "true",
    });
    // Only public variables are ever read here.
    expect(JSON.stringify(env)).not.toContain("postgresql");
  });
});
