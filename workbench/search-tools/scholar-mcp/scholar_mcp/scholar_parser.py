from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .models import PaperResult


_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_CITED_BY_RE = re.compile(r"Cited by\s+(\d+)", re.IGNORECASE)


def _extract_year(text: str | None) -> int | None:
    if not text:
        return None
    match = _YEAR_RE.search(text)
    if not match:
        return None
    return int(match.group(0))


def _extract_authors(meta_text: str | None) -> list[str]:
    if not meta_text:
        return []
    first_part = meta_text.split(" - ", 1)[0]
    return [part.strip() for part in first_part.split(",") if part.strip()]


def _extract_cited_by(raw_text: str | None) -> int | None:
    if not raw_text:
        return None
    match = _CITED_BY_RE.search(raw_text)
    if not match:
        return None
    return int(match.group(1))


def parse_topic_results(html: str, page_size: int) -> list[PaperResult]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("div.gs_r.gs_or.gs_scl")
    results: list[PaperResult] = []

    for row in rows:
        title_container = row.select_one("h3.gs_rt")
        if not title_container:
            continue

        title = title_container.get_text(" ", strip=True)
        if not title:
            continue

        link = title_container.select_one("a")
        url = link.get("href") if link else None

        meta_tag = row.select_one("div.gs_a")
        meta_text = meta_tag.get_text(" ", strip=True) if meta_tag else None

        snippet_tag = row.select_one("div.gs_rs")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else None

        cited_by: int | None = None
        for anchor in row.select("a"):
            cited_by = _extract_cited_by(anchor.get_text(" ", strip=True))
            if cited_by is not None:
                break

        results.append(
            PaperResult(
                title=title,
                authors=_extract_authors(meta_text),
                snippet=snippet,
                url=url,
                year=_extract_year(meta_text),
                cited_by=cited_by,
            )
        )

        if len(results) >= page_size:
            break

    return results
