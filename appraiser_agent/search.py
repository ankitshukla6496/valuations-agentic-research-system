"""Web search providers. Free `ddgs` by default; optional Tavily for quality."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from .config import config


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


def _classify(url: str) -> str:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if any(s in u for s in ("capterra.", "g2.com", "softwareadvice.", "trustradius.", "getapp.")):
        return "review_site"
    if any(s in u for s in ("reddit.com", "appraisersforum", "forum")):
        return "forum"
    if any(s in u for s in ("appraisalinstitute.org", ".org")) and "wikipedia" not in u:
        return "association"
    if any(s in u for s in ("blog", "medium.com", "substack.com")):
        return "blog"
    return "other"


def source_type_for(url: str) -> str:
    return _classify(url)


def _search_ddgs(query: str, max_results: int) -> list[SearchResult]:
    from ddgs import DDGS

    results: list[SearchResult] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href") or r.get("url", ""),
                    snippet=r.get("body", ""),
                )
            )
    return results


def _search_tavily(query: str, max_results: int) -> list[SearchResult]:
    resp = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": config.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        SearchResult(title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("content", ""))
        for r in data.get("results", [])
    ]


def search(query: str, max_results: int | None = None) -> list[SearchResult]:
    n = max_results or config.results_per_query
    try:
        if config.search_provider == "tavily":
            return _search_tavily(query, n)
        return _search_ddgs(query, n)
    except Exception as exc:  # noqa: BLE001 — search must never crash the run
        print(f"  [search] provider error for {query!r}: {exc}")
        return []
