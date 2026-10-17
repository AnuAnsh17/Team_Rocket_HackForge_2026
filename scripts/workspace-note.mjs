// Prints a short orientation note after `npm install` at the repository root.
//
// This exists because a new contributor's first `npm install` produces a large
// tree with no obvious next step. Keep it short and factual.
import { existsSync } from "node:fs";

const pythonHint = existsSync("backend/pyproject.toml")
  ? "  backend      cd backend && python -m venv .venv && .venv/Scripts/pip install -e '.[dev]'"
  : "  backend      (pyproject.toml not found)";

console.log(
  [
    "",
    "Proofline workspace installed (Node/TypeScript side only).",
    "",
    "Next steps:",
    pythonHint,
    "  database     npm run db:up",
    "  migrations   cd backend && .venv/Scripts/alembic upgrade head",
    "  api schema   npm run api:generate",
    "  portal       npm run portal:dev    (employee web portal,  :3000)",
    "  console      npm run console:dev   (internal console,     :3001)",
    "  mobile       npm run mobile:start  (Expo dev server)",
    "",
    "Python is NOT installed by this step. See docs/development-setup.md",
    "Nothing in this scaffold implements expense auditing yet; see",
    "docs/problem-statement-coverage.md for an honest status matrix.",
    "",
  ].join("\n"),
);
