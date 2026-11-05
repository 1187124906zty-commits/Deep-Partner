from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PaperResult:
    title: str
    authors: list[str]
    snippet: str | None
    url: str | None
    year: int | None
    cited_by: int | None
    source: str = "google_scholar"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ok(data: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "data": data}
    if warnings:
        payload["warnings"] = warnings
    return payload


def fail(
    code: str,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    if details:
        error["details"] = details
    return {"ok": False, "error": error}
