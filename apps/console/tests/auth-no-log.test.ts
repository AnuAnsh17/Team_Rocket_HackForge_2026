/**
 * Nothing that handles a credential may log one, and no private credential may appear in
 * the console's client-visible source.
 *
 * A runtime half drives the sign-in mapper with a deliberately leaky provider error and
 * asserts no console method was called with the password or the token. A static half reads
 * the auth modules and asserts they contain no `console.` call at all, so the invariant does
 * not depend on getting a log statement's argument list right, and that no private
 * credential name appears anywhere under `src/`, `app/` or `proxy.ts`.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it, vi } from "vitest";

import { describeSignInFailure, mapSignInError, redactSensitive } from "../src/lib/auth/messages";

const FAKE_JWT =
  "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEifQ.c2lnbmF0dXJlLXNlZ21lbnQ";
const FAKE_PASSWORD = "battery-staple-correct-horse";

const CONSOLE_ROOT = fileURLToPath(new URL("..", import.meta.url));

function collectFiles(relative: string): string[] {
  const absolute = join(CONSOLE_ROOT, relative);
  const found: string[] = [];
  for (const entry of readdirSync(absolute)) {
    const path = join(absolute, entry);
    if (statSync(path).isDirectory()) {
      found.push(...collectFiles(join(relative, entry)));
    } else if (/\.(ts|tsx)$/.test(entry)) {
      found.push(path);
    }
  }
  return found;
}

const CREDENTIAL_MODULES = [
  ...collectFiles("src/lib/auth"),
  ...collectFiles("src/lib/supabase"),
  join(CONSOLE_ROOT, "src/lib/api.ts"),
  join(CONSOLE_ROOT, "src/components/LoginForm.tsx"),
];

describe("credentials never reach a log", () => {
  it("does not call a console method while mapping a failed sign-in", () => {
    const spies = ["log", "info", "warn", "error", "debug"].map((method) =>
      vi.spyOn(console, method as "log"),
    );

    const leaky = {
      status: 401,
      message: `Invalid login credentials for password ${FAKE_PASSWORD} token ${FAKE_JWT}`,
    };
    const message = mapSignInError(leaky);
    const diagnostic = describeSignInFailure(leaky);

    expect(message).not.toContain(FAKE_PASSWORD);
    expect(diagnostic).not.toContain(FAKE_PASSWORD);
    expect(diagnostic).not.toContain(FAKE_JWT);
    for (const spy of spies) {
      const calls = spy.mock.calls.map((args) => args.map(String).join(" ")).join(" ");
      expect(calls).not.toContain(FAKE_PASSWORD);
      expect(calls).not.toContain(FAKE_JWT);
    }
    vi.restoreAllMocks();
  });

  it("redacts a token before it could be displayed anywhere", () => {
    expect(redactSensitive(`failed for ${FAKE_JWT}`)).not.toContain(FAKE_JWT);
  });
});

describe("credential-handling modules", () => {
  it("scans a non-empty set of modules", () => {
    // Guards against the scan below passing vacuously if a path ever moves.
    expect(CREDENTIAL_MODULES.length).toBeGreaterThanOrEqual(8);
    expect(CREDENTIAL_MODULES.some((file) => file.endsWith("api.ts"))).toBe(true);
    expect(CREDENTIAL_MODULES.some((file) => file.endsWith("supabase\\client.ts"))
      || CREDENTIAL_MODULES.some((file) => file.endsWith("supabase/client.ts"))).toBe(true);
  });

  it("contain no console logging at all", () => {
    for (const file of CREDENTIAL_MODULES) {
      const source = readFileSync(file, "utf-8");
      expect(source, `${file} must not log`).not.toMatch(/\bconsole\.[a-z]+\(/);
    }
  });

  it("reference no private credential name", () => {
    const forbidden = [
      "SUPABASE_SERVICE_ROLE",
      "SERVICE_ROLE_KEY",
      "JWT_SECRET",
      "DATABASE_URL",
      "SUPABASE_JWKS_URL",
      "SUPABASE_JWT_ISSUER",
    ];
    const sources = [
      ...collectFiles("src"),
      ...collectFiles("app"),
      join(CONSOLE_ROOT, "proxy.ts"),
    ];
    for (const file of sources) {
      const source = readFileSync(file, "utf-8");
      for (const name of forbidden) {
        expect(source, `${file} must not reference ${name}`).not.toContain(name);
      }
      // A private value must never be exposed through the NEXT_PUBLIC_ prefix.
      expect(source, `${file} exposes a server key`).not.toMatch(
        /NEXT_PUBLIC_[A-Z_]*(SERVICE|SECRET|PRIVATE)[A-Z_]*/,
      );
    }
  });

  it("reads only the public Supabase variables", () => {
    const config = readFileSync(join(CONSOLE_ROOT, "src/lib/supabase/config.ts"), "utf-8");
    expect(config).toContain("NEXT_PUBLIC_SUPABASE_URL");
    expect(config).toContain("NEXT_PUBLIC_SUPABASE_ANON_KEY");
  });
});
