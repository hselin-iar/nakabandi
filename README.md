# NAKABANDI

Prototype for predicting where cash-out is likely to happen after a reported fraud, so that
partner banks and law enforcement can act inside the interception window. Built as a modular
monolith with two simulated external systems. Specification lives in `DOC1.md` to `DOC4.md`.

## Prerequisites

- Python 3.11 (see `.python-version`) and [uv](https://docs.astral.sh/uv/)
- Node 24 LTS (see `.nvmrc`)

## Setup

```
uv sync
npm ci
uv run pre-commit install
npm run ci
```

`npm run ci` runs ruff, pyright, import-linter and pytest, then eslint, tsc, vitest and the web build.

## Running the full stack locally

The realistic way to see the dashboard populated (not just the tiny 5-row smoke fixture at
`data/seed/mini_ingest.jsonl`) is to run the simulator's live control server alongside the API,
then drive it from the Demo Console in the UI.

**Docker (recommended — matches the hosted topology, DOC 2 §2.2):**

```
cp infra/.env.example infra/.env   # fill in JWT_SECRET, API_SERVICE_KEY, etc.
cd infra && docker compose up --build
```

Then open the app, log in as a `demo_operator`, and use the Demo Console's Start/Speed controls.

**Without Docker (three terminals):**

```
export API_SERVICE_KEY=dev-service-key JWT_SECRET=$(openssl rand -base64 32)
uv run uvicorn nakabandi.main:app --app-dir apps/api/src --reload      # terminal 1: API on :8000
npm run dev:sim                                                        # terminal 2: simulator on :8100
npm run dev                                                            # terminal 3: web app
```

`npm run dev:sim` defaults to `http://localhost:8000` and the service key `dev-service-key`
(`worldsim live`'s own built-in fallbacks) — they must match whatever `API_SERVICE_KEY` the API
was started with.

## Data & attribution

The simulator's registry (banks, ATM/branch/agent locations, districts, response units) is
built from the real, curated data in `data/seed/` and `data/geo/` — see `data/geo/README.md`
for full sourcing and licensing. ATM and bank branch locations © OpenStreetMap contributors,
ODbL — this attribution is required by that data's licence and is also shown in the web app's
sidebar footer.

## Status

Backend and frontend are wired end-to-end; features are added step by step per track. See
`docs/state/track-{a,b,c,d,r}.md` for current per-track status and `DOC4.md` for the full plan.
