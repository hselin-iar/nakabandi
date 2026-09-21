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

## Status

Scaffold only. Features are added step by step; see `DOC4.md`.
