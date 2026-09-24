# TRACK C — Web & Bank Simulator
OWNER:            Web dev + coding agent
CURRENT_STEP:     none (Track C complete)
LAST_COMPLETED:   C9 — Hero-Flow E2E Test
STATUS:           CHECKPOINT
PAUSED_AT:        none
NEXT SYNC POINT:  CHECKPOINT 8 (Track C complete, ready for full integration)

STATUS is one of ACTIVE | RESUMING | BLOCKED | CHECKPOINT. Only this track's owner (and its agent) edits this file.
Update it after every completed step and before ending a session.

## Learnings
One line per entry, newest last: [Step] — what was found (a gotcha, a rejected approach and why, a decision not in the docs).
[C-onboarding] — machine confirmed green: node 24.18.0, uv 0.12.17, python 3.11.16; npm run ci passed.
[C1] — @vitejs/plugin-react requires a version-matched peer: v4 supports Vite ≤7, v6 supports Vite 8; always check peer deps before installing. Install inside apps/web, not at root — Vite loads vite.config.ts from the workspace's own node_modules context.
[C1] — schema.d.ts at C1 is hand-generated from LC-1/LC-2 Pydantic models; swap to openapi-typescript once FastAPI serves its OpenAPI document (A2). The `paths` type in client.ts is a placeholder `Record<string, never>` until then.
[C1] — eslint-plugin-boundaries 7.x uses `policies` not `element-types` (A1 learning confirmed); the `import/resolver` node extensions setting is essential — without it, extensionless TS imports go unchecked silently. Both were already in place from A1 merge.
[C1] — tailwind.preset.ts must not import from `tailwindcss` types at C1 (Tailwind not fully wired); use `Record<string, any>` until Tailwind is configured end-to-end. vite.config.ts must be excluded from tsconfig `include` to avoid peer-type resolution failures in the workspace context.
[C1] — RoleGuard route preservation verified via router location state redirect to /login and return upon quick-login.
[C2] — better-sqlite3 requires Visual Studio C++ build tools on Node 24 Windows x64. express.json with { verify: (req, res, buf) => req.rawBody = buf } must be used to capture rawBody synchronously for HMAC verification before parsing.
[C2/Sync 5] — Bank simulator merged to main; Sync 5 webhook callback verified; pulled full API schemas into web client.
[C3] — tsx extension required for files rendering JSX (useStream.tsx); React Testing Library cleanup() in afterEach avoids cross-test DOM bleed; openapi-fetch client typed via schema.d.ts paths contract.
[C4] — TanStack Query queries resolve asynchronously in RTL tests: always await findBy* for table rows and status badges; action modals update status to match StatusBadge config; review queue requires loaded alerts to display triage cards.
[C5] — MapLibre GL is completely isolated inside MapLibreAdapter.ts; zero CDN tile requests (bundled GeoJSON for UP, MH, RJ, HR); WebGL failure gracefully drops down to TableViewFallback without blank canvas; verbatimModuleSyntax requires explicit tsconfig types: ["geojson"].
[C6] — Cytoscape wrapper shared across clusters and cases via eslint boundaries exception; graph node capping at 200 preserves top priority entities with a "+N more" summary node; brief rendering uses safe React elements enforcing the mandatory FIR statutory disclaimer with zero XSS risk; role-gated masking strictly isolates raw account references from non-LEA principals.
[C7] — Recharts Tooltip `formatter` prop is typed as `Formatter<ValueType, NameType>` where ValueType is `string|number|...|undefined`; always guard with `Number(v ?? 0)` rather than typing `v: number`. ErrorState takes `{ error: UiError }` not `{ title, message }` — inline error divs are simpler when no retry handler needed. RTL getByText fails on compound spans (swatch+label+tag in one pill); add a data-testid on the label span itself.
[C8] — Proxied control path /sim-control/* strictly enforces demo_operator authorization (non-demo roles receive 403 on route and proxy); quick-login users are fetched dynamically from /auth/demo-users to prevent client bundle credential leak; in-memory request log captures real-time proxied payloads and responses for auditability; reset and seed controls are gated to admin role in hosted mode.
[C9] — Hero-flow Playwright test in apps/web/tests/e2e/hero-flow.spec.ts verifies full end-to-end integration: investigator quick-login -> live alert discovery -> hold request -> bank-sim console lien application -> alert timeline update -> bank_nodal scoped access verification; explicit preflight checks ensure stopped services fail fast with clear diagnostic errors instead of hanging until timeout. Vitest requires test.include and test.exclude to isolate playwright e2e specs from jsdom unit runner.


