// Regenerate the OpenAPI artifact and the TypeScript schema from the backend.
//
// Two artifacts are produced and both are COMMITTED on purpose:
//
//   openapi.json     the contract, as the running backend serves it
//   src/schema.d.ts  the generated TypeScript types derived from it
//
// Committing them means a client can type-check and CI can detect drift without
// booting the backend and without a database. `npm run check` regenerates both and
// fails if they differ from what is committed.
//
// This is the mechanism that stops the mobile app, the employee portal and the
// internal console from drifting apart, and stops any of them from hand-writing its
// own expense model.

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const packageRoot = resolve(here, "..");
const repoRoot = resolve(packageRoot, "..", "..");
const backendRoot = join(repoRoot, "backend");

const OPENAPI_PATH = join(packageRoot, "openapi.json");
const SCHEMA_PATH = join(packageRoot, "src", "schema.d.ts");

// The backend needs an interpreter. Prefer the project virtualenv so the generated
// contract matches the pinned dependencies rather than whatever is on PATH.
function backendPython() {
  const candidates = [
    join(backendRoot, ".venv", "Scripts", "python.exe"),
    join(backendRoot, ".venv", "bin", "python"),
  ];
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return process.platform === "win32" ? "python" : "python3";
}

export async function generateOpenApiJson() {
  if (!existsSync(join(backendRoot, "scripts", "export_openapi.py"))) {
    throw new Error(
      `Cannot find backend/scripts/export_openapi.py. Expected the backend at ${backendRoot}.`,
    );
  }
  execFileSync(backendPython(), ["scripts/export_openapi.py", OPENAPI_PATH], {
    cwd: backendRoot,
    stdio: ["ignore", "pipe", "inherit"],
    encoding: "utf-8",
  });
}

export async function generateSchemaTypes() {
  // openapi-typescript is imported rather than shelled out so the output is written
  // here, with a stable trailing newline, instead of depending on CLI formatting.
  const { default: openapiTS, astToString } = await import("openapi-typescript");
  const ast = await openapiTS(new URL(`file://${OPENAPI_PATH}`));
  const output = astToString(ast);
  await mkdir(dirname(SCHEMA_PATH), { recursive: true });
  await writeFile(SCHEMA_PATH, output.endsWith("\n") ? output : `${output}\n`, "utf-8");
}

export const paths = { OPENAPI_PATH, SCHEMA_PATH };

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith("generate.mjs")) {
  await generateOpenApiJson();
  await generateSchemaTypes();
  console.log("Regenerated packages/api-client/openapi.json and src/schema.d.ts");
}
