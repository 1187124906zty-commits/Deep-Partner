from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import Settings
from .models import PaperResult
from .scholar_parser import parse_topic_results


SEARCH_URL = "https://scholar.google.com/scholar"


@dataclass
class AuthorPapersResponse:
    author_name: str
    author_id: str | None
    affiliation: str | None
    papers: list[PaperResult]
    next_cursor: str | None


class ScholarClientError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


class ScholarClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self._next_request_at = 0.0

    def _wait_for_slot(self) -> None:
        now = time.monotonic()
        if now < self._next_request_at:
            time.sleep(self._next_request_at - now)

        delay = self.settings.min_delay_seconds + random.uniform(0.0, 0.35)
        self._next_request_at = time.monotonic() + delay

    def _request(self, url: str, params: dict[str, Any]) -> str:
        proxy_config = (
            {"http": self.settings.proxy_url, "https": self.settings.proxy_url}
            if self.settings.proxy_url
            else None
        )

        last_error: Exception | None = None

        for attempt in range(self.settings.max_retries + 1):
            self._wait_for_slot()
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.settings.timeout_seconds,
                    proxies=proxy_config,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.settings.max_retries:
                    break
                time.sleep(self.settings.retry_backoff_seconds * (attempt + 1))
                continue

            if response.status_code == 200:
                return response.text

            if response.status_code in (429, 503):
                if attempt >= self.settings.max_retries:
                    raise ScholarClientError(
                        code="rate_limited",
                        message="Google Scholar rate-limited the request.",
                        retryable=True,
                        details={"status_code": response.status_code},
                    )
                backoff = self.settings.retry_backoff_seconds * (2**attempt)
                time.sleep(backoff)
                continue

            if response.status_code == 403:
                raise ScholarClientError(
                    code="blocked",
                    message="Request blocked by Google Scholar.",
                    retryable=True,
                    details={"status_code": 403},
                )

            if attempt >= self.settings.max_retries:
                raise ScholarClientError(
                    code="http_error",
                    message=f"Scholar request failed with status {response.status_code}.",
                    retryable=False,
                    details={"status_code": response.status_code},
                )

            time.sleep(self.settings.retry_backoff_seconds * (attempt + 1))

        raise ScholarClientError(
            code="network_error",
            message="Network request to Google Scholar failed.",
            retryable=True,
            details={"reason": str(last_error)} if last_error else None,
        )

    def search_topic(
        self,
        query: str,
        page_size: int,
        start: int,
        year_min: int | None = None,
        year_max: int | None = None,
    ) -> tuple[list[PaperResult], str | None]:
        params: dict[str, Any] = {
            "hl": "en",
            "q": query,
            "start": start,
        }
        if year_min is not None:
            params["as_ylo"] = year_min
        if year_max is not None:
            params["as_yhi"] = year_max

        html = self._request(SEARCH_URL, params)
        papers = parse_topic_results(html=html, page_size=page_size)
        next_cursor = str(start + page_size) if len(papers) >= page_size else None
        return papers, next_cursor

    def get_author_papers(
        self,
        author_query: str,
        page_size: int,
        start: int,
    ) -> AuthorPapersResponse:
        author_query = author_query.strip()
        if not author_query:
            raise ScholarClientError(
                code="invalid_request",
                message="Author query cannot be empty.",
                retryable=False,
            )

        html = self._request(
            SEARCH_URL,
            params={
                "hl": "en",
                "q": author_query,
                "as_sauthors": author_query,
                "start": start,
            },
        )

        papers = [
            item
            for item in parse_topic_results(html=html, page_size=page_size + 3)
            if not item.title.lower().startswith("user profiles for")
        ][:page_size]

        if not papers:
            raise ScholarClientError(
                code="author_not_found",
                message=f"No papers found for author '{author_query}'.",
                retryable=False,
            )

        next_cursor = str(start + page_size) if len(papers) >= page_size else None

        return AuthorPapersResponse(
            author_name=author_query,
            author_id=None,
            affiliation=None,
            papers=papers,
            next_cursor=next_cursor,
        )
