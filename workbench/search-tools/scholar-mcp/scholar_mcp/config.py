from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class Settings:
    user_agent: str = DEFAULT_USER_AGENT
    timeout_seconds: float = 20.0
    min_delay_seconds: float = 1.2
    max_retries: int = 2
    retry_backoff_seconds: float = 1.5
    proxy_url: str | None = None
    max_page_size: int = 20


def _read_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _read_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def load_settings() -> Settings:
    return Settings(
        user_agent=os.getenv("SCHOLAR_USER_AGENT", DEFAULT_USER_AGENT),
        timeout_seconds=max(3.0, _read_float("SCHOLAR_TIMEOUT", 20.0)),
        min_delay_seconds=max(0.5, _read_float("SCHOLAR_MIN_DELAY", 1.2)),
        max_retries=max(0, _read_int("SCHOLAR_MAX_RETRIES", 2)),
        retry_backoff_seconds=max(0.5, _read_float("SCHOLAR_RETRY_BACKOFF", 1.5)),
        proxy_url=os.getenv("SCHOLAR_PROXY_URL") or None,
        max_page_size=max(1, _read_int("SCHOLAR_MAX_PAGE_SIZE", 20)),
    )
