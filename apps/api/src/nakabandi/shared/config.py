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

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# DOC 2 §2.7 "Public exposure": at most 25 concurrent SSE streams; world auto-pauses after 15
# minutes without a viewer; nightly reset. The control rate is not numbered in the DOCs.
HOSTED_MAX_SSE_STREAMS = 25
HOSTED_AUTO_PAUSE_AFTER_MIN = 15.0
HOSTED_NIGHTLY_RESET_AT = "03:00"
HOSTED_CONTROL_RATE_PER_MIN = 30


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
    # ---- hosted-demo protections (DOC 2 §2.7 "Public exposure"; DOC 4 A11) --------------------
    # Configuration only through the environment. `hosted_demo` switches on the protections'
    # DEFAULTS; each can still be set explicitly (0 / unset-with-hosted-off means "not enforced").
    # Nothing product-specific may depend on any of these being on.
    hosted_demo: bool = False
    demo_users_enabled: bool = True
    """Serve GET /auth/demo-users (plaintext demo credentials; DOC 2 §2.8 T19). True by default so
    local, offline and hosted DEMOS work; set false for any deployment that is not a demo."""
    max_sse_streams: int | None = None
    control_rate_per_min: int | None = None
    auto_pause_after_min: float | None = None
    nightly_reset_at: str | None = None  # "HH:MM", UTC
    sim_control_url: str | None = None
    """world-sim's control API base (e.g. http://world-sim:8100/control): auto-pause and the
    nightly reset call it. Unset = the API never touches the simulator."""
    seed_file: Path = Field(default=Path("data/seed/mini_ingest.jsonl"))
    static_dir: Path | None = Field(default=None, validation_alias="STATIC_DIR")
    """The built SPA's directory (DOC 4 Step A5: "api container, SPA static files"). Unset
    outside the Docker image, where Dockerfile.api builds apps/web and sets it."""

    @field_validator("nightly_reset_at")
    @classmethod
    def _hh_mm(cls, v: str | None) -> str | None:
        if not v:  # unset, or empty: an explicit way to switch the reset off
            return v
        try:
            hh, mm = v.split(":")
            if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
                raise ValueError
        except ValueError as exc:
            raise ValueError("nightly_reset_at must be HH:MM (UTC), e.g. 03:00") from exc
        return v

    @property
    def effective_max_sse_streams(self) -> int:
        """Concurrent SSE streams allowed; 0 = unlimited. Hosted default 25 (DOC 2 §2.7)."""
        if self.max_sse_streams is not None:
            return self.max_sse_streams
        return HOSTED_MAX_SSE_STREAMS if self.hosted_demo else 0

    @property
    def effective_control_rate_per_min(self) -> int:
        """Calls per minute per client to the control-gate endpoint; 0 = unlimited."""
        if self.control_rate_per_min is not None:
            return self.control_rate_per_min
        return HOSTED_CONTROL_RATE_PER_MIN if self.hosted_demo else 0

    @property
    def effective_auto_pause_after_min(self) -> float:
        """Minutes without a viewer before the world is paused; 0 = never. Hosted default 15."""
        if self.auto_pause_after_min is not None:
            return self.auto_pause_after_min
        return HOSTED_AUTO_PAUSE_AFTER_MIN if self.hosted_demo else 0.0

    @property
    def effective_nightly_reset_at(self) -> str | None:
        if self.nightly_reset_at is not None:
            return self.nightly_reset_at or None
        return HOSTED_NIGHTLY_RESET_AT if self.hosted_demo else None


def get_settings() -> Settings:
    """Reads Settings from the environment fresh each call; process startup is the only hot
    path and this is cheap. No caching here avoids stale settings surviving a config reload."""
    return Settings()  # type: ignore[call-arg]  # pydantic-settings fills required fields from env
