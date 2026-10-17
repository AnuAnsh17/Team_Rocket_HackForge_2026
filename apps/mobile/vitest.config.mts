import { defineConfig } from "vitest/config";

/**
 * Vitest configuration for the mobile app.
 *
 * The app's tsconfig.json extends `expo/tsconfig.base`, which the test runner's
 * transformer cannot resolve (it is an Expo package export, not a file path). Rather than
 * maintaining a second tsconfig that would drift from the real one, the compiler options
 * the transformer actually needs are supplied inline, so a test run never reads the Expo
 * base at all.
 */
export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
  esbuild: {
    tsconfigRaw: JSON.stringify({
      compilerOptions: {
        target: "es2022",
        jsx: "react-jsx",
        strict: true,
        useDefineForClassFields: true,
      },
    }),
  },
});
