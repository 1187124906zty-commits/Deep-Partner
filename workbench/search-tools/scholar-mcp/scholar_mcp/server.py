from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import load_settings
from .models import fail, ok
from .scholar_client import ScholarClient, ScholarClientError


settings = load_settings()
client = ScholarClient(settings)
mcp = FastMCP("Scholar MCP")


def _parse_cursor(cursor: str | None) -> int:
    if cursor is None or cursor == "":
        return 0
    try:
        value = int(cursor)
    except ValueError as exc:
        raise ValueError("cursor must be an integer offset string") from exc
    if value < 0:
        raise ValueError("cursor must be zero or greater")
    return value


def _normalize_page_size(page_size: int) -> int:
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    return min(page_size, settings.max_page_size)


@mcp.tool()
def search_papers_by_topic(
    query: str,
    page_size: int = 10,
    cursor: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
) -> dict[str, Any]:
    """Search Google Scholar papers by topic keywords."""
    query = query.strip()
    if not query:
        return fail("invalid_request", "query cannot be empty", retryable=False)

    if year_min is not None and year_max is not None and year_min > year_max:
        return fail(
            "invalid_request",
            "year_min cannot be greater than year_max",
            retryable=False,
        )

    try:
        start = _parse_cursor(cursor)
        size = _normalize_page_size(page_size)
    except ValueError as exc:
        return fail("invalid_request", str(exc), retryable=False)

    try:
        papers, next_cursor = client.search_topic(
            query=query,
            page_size=size,
            start=start,
            year_min=year_min,
            year_max=year_max,
        )
    except ScholarClientError as exc:
        return fail(exc.code, exc.message, retryable=exc.retryable, details=exc.details)

    return ok(
        {
            "query": query,
            "page_size": size,
            "cursor": str(start),
            "next_cursor": next_cursor,
            "source": "google_scholar",
            "results": [paper.to_dict() for paper in papers],
            "fetched_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
    )


@mcp.tool()
def get_author_papers(
    author: str,
    page_size: int = 10,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Get papers filtered by author name from Google Scholar search."""
    author = author.strip()
    if not author:
        return fail("invalid_request", "author cannot be empty", retryable=False)

    try:
        start = _parse_cursor(cursor)
        size = _normalize_page_size(page_size)
    except ValueError as exc:
        return fail("invalid_request", str(exc), retryable=False)

    try:
        response = client.get_author_papers(author_query=author, page_size=size, start=start)
    except ScholarClientError as exc:
        return fail(exc.code, exc.message, retryable=exc.retryable, details=exc.details)

    return ok(
        {
            "author": {
                "name": response.author_name,
                "id": response.author_id,
                "affiliation": response.affiliation,
            },
            "page_size": size,
            "cursor": str(start),
            "next_cursor": response.next_cursor,
            "source": "google_scholar",
            "results": [paper.to_dict() for paper in response.papers],
            "fetched_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
