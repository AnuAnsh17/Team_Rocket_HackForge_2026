/**
 * Demo gating by the real environment.
 *
 * The modules are re-imported with `vi.stubEnv` so the console's build-time constants are
 * re-evaluated, which is the only way to assert both directions of the rule: the demo actor
 * header is sent in demo mode, and is not sent at all once a Supabase project is configured.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ACTOR = "99999999-9999-4999-8999-999999999999";

function installWindow(localStorageValue: string | null) {
  (globalThis as unknown as Record<string, unknown>).window = {
    localStorage: {
      getItem: () => localStorageValue,
      setItem: () => {},
      removeItem: () => {},
    },
  };
}

function clearWindow() {
  delete (globalThis as unknown as Record<string, unknown>).window;
}

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
  clearWindow();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
  clearWindow();
});

describe("demo identity gating", () => {
  it("sends no demo header when a Supabase project is configured", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://project-ref.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "public-anon-key-placeholder");
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "true");
    installWindow(ACTOR);

    const api = await import("../src/lib/api");

    expect(api.SUPABASE_CONFIGURED).toBe(true);
    expect(api.DEMO_MODE_ENABLED).toBe(true);
    // The flag alone is not enough: a configured project disables the demo path.
    expect(api.DEMO_MODE_ACTIVE).toBe(false);
    expect(api.readDemoActorId()).toBeNull();
    expect(api.consoleApiOptions().getDemoActorId?.()).toBeNull();
  });

  it("sends the demo header when demo mode is the only configured path", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "true");
    installWindow(ACTOR);

    const api = await import("../src/lib/api");

    expect(api.SUPABASE_CONFIGURED).toBe(false);
    expect(api.DEMO_MODE_ACTIVE).toBe(true);
    expect(api.readDemoActorId()).toBe(ACTOR);
    expect(api.consoleApiOptions().getDemoActorId?.()).toBe(ACTOR);
  });

  it("sends nothing when demo mode is off and no project is configured", async () => {
    installWindow(ACTOR);

    const api = await import("../src/lib/api");

    expect(api.DEMO_MODE_ACTIVE).toBe(false);
    expect(api.DEMO_MODE_ENABLED).toBe(false);
    expect(api.readDemoActorId()).toBeNull();
    expect(api.consoleApiOptions().getDemoActorId?.()).toBeNull();
  });

  it("never registers a token while no project is configured", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "true");
    const api = await import("../src/lib/api");
    // Nothing has registered a provider, so no bearer header can be produced in demo mode.
    expect(await api.readAccessToken()).toBeNull();
  });
});
