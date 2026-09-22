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


def get_settings() -> Settings:
    """Reads Settings from the environment fresh each call; process startup is the only hot
    path and this is cheap. No caching here avoids stale settings surviving a config reload."""
    return Settings()  # type: ignore[call-arg]  # pydantic-settings fills required fields from env
