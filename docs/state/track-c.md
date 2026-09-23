# TRACK C — Web & Bank Simulator
OWNER:            Web dev + coding agent
CURRENT_STEP:     C2 — Bank Gateway Simulator
LAST_COMPLETED:   C1 — Web Scaffold & Shell
STATUS:           ACTIVE
PAUSED_AT:        none
NEXT SYNC POINT:  SYNC 5 (after A8 + C2); SYNC 6, after D1 (DOC4 §4.1a)

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
