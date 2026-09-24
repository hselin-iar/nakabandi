"""Service-key auth dependency for /ingest/* (DOC 2 §2.4: "INGEST (machine clients only:
service API key)"). No header name is specified in the DOCs; `X-Nakabandi-Service-Key` is
chosen here to match the `X-Nakabandi-*` naming already used for the LC-6 bank webhook headers.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, Header

from nakabandi.shared import Settings, Unauthenticated, get_settings


def require_service_key(
    x_nakabandi_service_key: str | None = Header(default=None),
    x_service_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    key = x_nakabandi_service_key or x_service_key
    if key is None and authorization and authorization.startswith("Bearer "):
        key = authorization[len("Bearer ") :].strip()
    if key is None or not secrets.compare_digest(key, settings.service_api_key):
        raise Unauthenticated("SERVICE_KEY_INVALID", "a valid service key is required")
