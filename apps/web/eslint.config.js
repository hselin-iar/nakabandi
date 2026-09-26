import js from "@eslint/js";
import boundaries from "eslint-plugin-boundaries";
import tseslint from "typescript-eslint";

// DOC 2 §2.6: web features do not import each other; they import only from shared/*.
export default tseslint.config(
  { ignores: ["dist"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { boundaries },
    settings: {
      // Lets the plugin resolve extensionless TypeScript imports; without it imports go unchecked.
      "import/resolver": { node: { extensions: [".ts", ".tsx"] } },
      "boundaries/elements": [
        { type: "feature", pattern: "src/features/*", capture: ["name"] },
        { type: "shared", pattern: "src/shared/*", capture: ["area"] },
      ],
    },
    rules: {
      // Underscore-prefixed names in a destructure are an intentional discard (e.g.
      // `const { from: _f, ...rest } = filters` to drop a key), not dead code.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "boundaries/dependencies": [
        2,
        {
          default: "disallow",
          policies: [
            {
              from: { element: { type: "feature" } },
              allow: { to: { element: { type: "shared" } } },
            },
            {
              // DOC 4 §C6: Cytoscape wrapper is shared between clusters and cases (built once in clusters, imported from cases)
              from: { element: { type: "feature", name: "cases" } },
              allow: { to: { element: { type: "feature", name: "clusters" } } },
            },
            {
              // Frontend Strategy §4.5: System Integrity composes Evaluation/Ops/Audit as
              // tabs under one destination, rather than duplicating their pages.
              from: { element: { type: "feature", name: "system" } },
              allow: {
                to: {
                  element: {
                    type: "feature",
                    name: ["evaluation", "ops", "audit"],
                  },
                },
              },
            },
            {
              from: { element: { type: "shared" } },
              allow: { to: { element: { type: "shared" } } },
            },
          ],
        },
      ],
    },
  },
);
