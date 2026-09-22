"""A default API_SERVICE_KEY so importing `nakabandi.main` (which builds a module-level `app`
via `create_app()`, the uvicorn `module:variable` convention for Step A5) never fails Settings
validation during test collection. Individual tests still call `create_app()` themselves with
their own monkeypatched env (a fresh DB per test), never the pre-built module-level `app`.
"""

import os

os.environ.setdefault("API_SERVICE_KEY", "test-only-service-key")
