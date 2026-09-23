"""Settings: process configuration from the environment only (DOC 3 Shared Kernel).

Fields are added as later steps need them (never invented ahead of the step that needs them,
AP-08); a missing or malformed value fails fast at startup rather than falling back silently.

`service_api_key` is read from the bare `API_SERVICE_KEY` variable (DOC 4 §4.4's deployment
env var list; also apps/bank-sim's own `API_SERVICE_KEY`, DOC 3 Bank Gateway Simulator
config.ts): the same secret authenticates every machine client across both processes, so it
is not prefixed like the fields below it that DOC 4 §4.4 does not name.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NAKABANDI_", env_file=None, extra="forbid")

    environment: str = "dev"
    policy_path: Path = Field(default=Path("config/policy.yaml"))
    service_api_key: str = Field(validation_alias="API_SERVICE_KEY")
    database_url: str = Field(default="sqlite:///nakabandi.db", validation_alias="DATABASE_URL")
    jwt_secret: str = Field(validation_alias="JWT_SECRET")
    webhook_secret: str | None = Field(default=None, validation_alias="WEBHOOK_SECRET")
    """HMAC secret for the LC-6 bank webhook; the SAME value apps/bank-sim verifies with
    (infra/.env.example). Optional so the API boots without a bank; a hold_request then
    dead-letters visibly in the outbox instead of being sent unsigned."""
    bank_webhook_url: str | None = None
    """Full URL of the bank gateway's POST /webhooks/nakabandi (LC-6)."""
    smtp_host: str | None = None
    smtp_port: int = 1025
    sms_provider_url: str | None = None
    sms_provider_key: str | None = None
    outbox_worker_enabled: bool = True
    """Run the in-process outbox worker (DOC 2 §2.2). Tests turn it off and call run_once."""
    timer_worker_enabled: bool = True
    """Run the in-process timer driver (escalation, expiry, lien review; DOC 2 §2.2). Tests turn it
    off and drive `AlertService.fire_due_timers` themselves."""
    static_dir: Path | None = Field(default=None, validation_alias="STATIC_DIR")
    """The built SPA's directory (DOC 4 Step A5: "api container, SPA static files"). Unset
    outside the Docker image, where Dockerfile.api builds apps/web and sets it."""


def get_settings() -> Settings:
    """Reads Settings from the environment fresh each call; process startup is the only hot
    path and this is cheap. No caching here avoids stale settings surviving a config reload."""
    return Settings()  # type: ignore[call-arg]  # pydantic-settings fills required fields from env
