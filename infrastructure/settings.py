from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Infrastructure settings may be imported before utils.config_handler. Loading
# the root .env here makes configuration independent from Python import order.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PlatformSettings:
    """Central runtime settings.

    The default values keep the project runnable for a learner without Docker.
    Setting DATABASE_URL and REDIS_URL enables the production-style adapters.
    """

    database_url: str = os.getenv("DATABASE_URL", "").strip()
    redis_url: str = os.getenv("REDIS_URL", "").strip()
    enable_platform_db: bool = _as_bool(os.getenv("ENABLE_PLATFORM_DB"), False)
    enable_langgraph: bool = _as_bool(os.getenv("ENABLE_LANGGRAPH"), True)
    secure_cookie: bool = _as_bool(os.getenv("SECURE_COOKIE"), False)
    agent_event_ttl_seconds: int = int(os.getenv("AGENT_EVENT_TTL_SECONDS", "3600"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "15"))


platform_settings = PlatformSettings()
