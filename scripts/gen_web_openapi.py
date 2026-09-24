#!/usr/bin/env python3
"""Export the API's real OpenAPI document to apps/web/openapi.json, with the `/api/v1` prefix
stripped so paths match apps/web/src/shared/api/client.ts's `baseUrl: "/api/v1"` convention.

Run via `npm run types` (DOC 4 Sync 4: "no OpenAPI -> schema.d.ts step" — this is that step),
which pipes the result through openapi-typescript into schema.d.ts. Needs no running server:
constructs the app in-process and reads its own generated spec.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("API_SERVICE_KEY", "codegen-only-not-a-real-key")
os.environ.setdefault("JWT_SECRET", "codegen-only-not-a-real-secret-32-bytes-ok")

from nakabandi.main import create_app  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "apps" / "web" / "openapi.json"


def main() -> None:
    spec = create_app().openapi()
    spec["paths"] = {path.removeprefix("/api/v1"): value for path, value in spec["paths"].items()}
    OUT.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(spec['paths'])} paths)")


if __name__ == "__main__":
    main()
