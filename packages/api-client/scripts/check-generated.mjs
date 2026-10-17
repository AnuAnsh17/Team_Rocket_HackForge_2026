// Fail if the committed contract artifacts are stale.
//
// This is the contract-drift guard. It regenerates the OpenAPI document and the
// TypeScript schema into temporary files and compares them byte for byte with what is
// committed. A backend change that alters the contract without regenerating the client
// therefore fails CI, instead of surfacing later as a type error in one of three
// clients - or worse, as a runtime surprise.

import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { generateOpenApiJson, generateSchemaTypes, paths } from "./generate.mjs";

const { OPENAPI_PATH, SCHEMA_PATH } = paths;

async function readOrNull(path) {
  try {
    return await readFile(path, "utf-8");
  } catch {
    return null;
  }
}

async function firstDifference(label, committed, regenerated) {
  if (committed === regenerated) return null;
  if (committed === null) return `${label}: not committed (run \`npm run generate\`)`;
  if (committed === regenerated) return null;

  const committedLines = committed.split("\n");
  const regeneratedLines = regenerated.split("\n");
  const max = Math.max(committedLines.length, regeneratedLines.length);
  for (let i = 0; i < max; i += 1) {
    if (committedLines[i] !== regeneratedLines[i]) {
      return [
        `${label}: differs from the committed copy.`,
        `  first difference at line ${i + 1}:`,
        `    committed:   ${JSON.stringify(committedLines[i] ?? "<end of file>")}`,
        `    regenerated: ${JSON.stringify(regeneratedLines[i] ?? "<end of file>")}`,
      ].join("\n");
    }
  }
  return `${label}: differs from the committed copy.`;
}

const committedOpenApi = await readOrNull(OPENAPI_PATH);
const committedSchema = await readOrNull(SCHEMA_PATH);

// Regenerate to sound out the backend, then compare. The committed files are restored
// afterwards so a failed check never leaves a modified working tree.
const scratch = await mkdtemp(join(tmpdir(), "proofline-contract-"));
try {
  await generateOpenApiJson();
  const regeneratedOpenApi = await readOrNull(OPENAPI_PATH);
  await generateSchemaTypes();
  const regeneratedSchema = await readOrNull(SCHEMA_PATH);

  // Restore the committed artifacts immediately.
  if (committedOpenApi !== null) await writeFile(OPENAPI_PATH, committedOpenApi, "utf-8");
  if (committedSchema !== null) await writeFile(SCHEMA_PATH, committedSchema, "utf-8");

  const problems = [
    await firstDifference("openapi.json", committedOpenApi, regeneratedOpenApi),
    await firstDifference("src/schema.d.ts", committedSchema, regeneratedSchema),
  ].filter(Boolean);

  if (problems.length > 0) {
    console.error("Contract artifacts are out of date:\n");
    for (const problem of problems) console.error(problem);
    console.error("\nRun `npm run api:generate` and commit the result.");
    process.exitCode = 1;
  } else {
    console.log("Contract artifacts are up to date.");
  }
} finally {
  await rm(scratch, { recursive: true, force: true });
}
