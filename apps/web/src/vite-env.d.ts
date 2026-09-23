/**
 * vite-env.d.ts — Vite client type declarations.
 * Also declares CSS module side-effect imports so TypeScript doesn't error.
 */

/// <reference types="vite/client" />

// Allow CSS side-effect imports (e.g. `import './tokens.css'`)
declare module "*.css" {
  const content: Record<string, string>;
  export default content;
}
