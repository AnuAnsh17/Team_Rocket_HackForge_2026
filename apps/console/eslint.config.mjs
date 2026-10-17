// Flat ESLint configuration.
//
// typescript-eslint's recommended set is used rather than eslint-config-next, so the
// rules are explicit and do not depend on a framework preset's internals.
import tseslint from "typescript-eslint";

export default [
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"],
  },
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    rules: {
      // Unused arguments are common in placeholder component signatures.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
];
