import tseslint from "typescript-eslint";

export default [
  {
    ignores: ["node_modules/**", ".expo/**", "dist/**", "expo-env.d.ts"],
  },
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    // Metro loads its configuration with require(), so this file is genuinely CommonJS.
    // The rule exists to catch require() in application code, which would break bundling.
    files: ["metro.config.js"],
    rules: { "@typescript-eslint/no-require-imports": "off" },
  },
];
