"""Settings: process configuration from the environment only (DOC 3 Shared Kernel).

Minimal for this step: just enough to locate the policy file Policy.load() reads. Fields are
added as later steps need them (never invented ahead of the step that needs them, AP-08); a
missing or malformed value fails fast at startup rather than falling back silently.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NAKABANDI_", env_file=None, extra="forbid")

    environment: str = "dev"
    policy_path: Path = Field(default=Path("config/policy.yaml"))


def get_settings() -> Settings:
    """Reads Settings from the environment fresh each call; process startup is the only hot
    path and this is cheap. No caching here avoids stale settings surviving a config reload."""
    return Settings()
