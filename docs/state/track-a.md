# TRACK A — Platform & Integration
OWNER:            Systems lead + coding agent (Integration Owner)
CURRENT_STEP:     A2 — Shared Kernel & Contracts
LAST_COMPLETED:   A1 — Repo Scaffold & Guardrails. Evidence: green CI run https://github.com/hselin-iar/nakabandi/actions/runs/35639465047 (pull_request; the push run is .../35639464810), head 6338620; import-linter failure proven locally in the working tree: "nakabandi.graph.domain is not allowed to import sqlalchemy: nakabandi.graph.domain._tmp_violation -> sqlalchemy (l.1)", then green again after removing the file; machine confirmations 1/4 (Integration Owner's machine) with 3 pending. The four-machine line was waived as a gate by the Integration Owner; each teammate's own `npm run ci` is their onboarding gate.
STATUS:           ACTIVE
PAUSED_AT:        none
NEXT SYNC POINT:  SYNC 1, after A2 (DOC4 §4.1a)

STATUS is one of ACTIVE | RESUMING | BLOCKED | CHECKPOINT. Only this track's owner (and its agent) edits this file.
Update it after every completed step and before ending a session.

## Learnings
One line per entry, newest last: [Step] — what was found (a gotcha, a rejected approach and why, a decision not in the docs).
[A1] — Toolchain: uv 0.12.17 (brew), Python 3.11.16 via `uv python install`, gitleaks 8.30.1 (brew), Node 24.6.0 (Node 20 is end-of-life; the Integration Owner pinned "Node 24 LTS" in the docs, commit f56f1ac). pre-commit is a workspace dev dependency in the root pyproject (pinned by uv.lock, installed by `uv sync`, then `uv run pre-commit install`), not a `uv tool`, so all machines get the same version.
[A1] — import-linter can only resolve forbidden external packages that are installed, so sqlalchemy, fastapi, httpx and requests sit in the root `dev` dependency group purely for the domain-purity contract. Runtime dependencies are added per step. Facade-only rule = one forbidden contract per module with `nakabandi.<other>.**` and `allow_indirect_imports = True`; layers contract marks `interfaces` and `infrastructure` optional because not every module has them. All 17 contracts were shown to fire on deliberate violations; a facade import correctly passes.
[A1] — NOT encoded: the DOC 2 §2.6 row "only evaluation may import the oracle client". `nakabandi.evaluation.oracle_client` does not exist yet (Track B, B7), and a forbidden contract needs the module to exist. Until then the facade rule already blocks every non-evaluation module from reaching it, and `main.py` may not import evaluation. Add an explicit contract when B7 creates the file. Also not encodable: "only pipeline and main.py import several facades in sequence"; only "no module imports pipeline" is enforced.
[A1] — eslint-plugin-boundaries 7.2 uses the `boundaries/dependencies` rule with `policies` (not the old `element-types`). It silently skips extensionless TypeScript imports unless `settings["import/resolver"] = { node: { extensions: [".ts", ".tsx"] } }` is set; without it the cross-feature rule reported nothing at all. No extra resolver package was needed (eslint-import-resolver-node ships with the plugin). Always test a boundary rule with a deliberate violation before trusting a green lint.
[A1] — Root scripts `dev`, `types`, `seed`, `reset`, `sweep` are placeholders (`scripts/not-yet.mjs`, exit 0 with a message) until their steps land. `.env.example` lives in infra/ (DOC 2 layout) and lists only the four bank-sim names DOC 3 defines; API Settings names are added at A2.
[A1] — Shell gotcha: the dev shell is zsh, which does not word-split unquoted variables, so `for m in $list` loops and `uv run "cmd args"` silently misbehave. Use literal lists or arrays.
