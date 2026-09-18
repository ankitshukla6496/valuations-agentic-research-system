"""The research agent orchestrator.

Pipeline:
  1. Plan diverse search queries (Claude).
  2. Seed with tools Claude already knows.
  3. Search the web; collect candidate source URLs across many source types.
  4. Visit + screenshot each source; extract any tools mentioned (Claude).
  5. Canonicalize / merge tool names.
  6. For the top tools, capture the official website + synthesize a clean record.
  7. Write catalog.json + CATALOG.md into output/<run-id>/.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import catalog
from .browser import Browser
from .config import config
from .llm import LLM
from .models import Source, Tool, slugify
from .search import search, source_type_for

ProgressFn = Callable[[str], None]

DEFAULT_SEEDS = [
    "real estate appraisal software",
    "property valuation tools for appraisers",
    "URAR / UAD form-filling software",
    "appraisal comps and market analytics tools",
    "mobile home inspection apps for appraisers",
    "appraisal workflow / order management software",
]

# How many discovery pages to visit+screenshot before the per-tool deep dive.
MAX_DISCOVERY_PAGES = 40


class Agent:
    def __init__(self, seeds: list[str] | None = None, progress: ProgressFn | None = None):
        config.validate()
        self.seeds = seeds or DEFAULT_SEEDS
        self.llm = LLM()
        self._progress = progress or (lambda msg: print(msg))
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = config.output_dir / f"run-{run_id}"
        self.shots_dir = self.run_dir / "screenshots"

    def log(self, msg: str) -> None:
        self._progress(msg)

    # ------------------------------------------------------------------
    def run(self) -> dict:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log(f"▶ Run started · output → {self.run_dir}")

        self.log("① Planning search queries…")
        queries = self.llm.plan_search_queries(self.seeds)
        self.log(f"   {len(queries)} queries planned.")

        self.log("② Asking the model for tools it already knows…")
        seeded = self.llm.known_tools(self.seeds)
        self.log(f"   {len(seeded)} seed tools.")

        # candidate URLs -> source_type
        self.log("③ Searching the web across all source types…")
        candidate_urls: dict[str, str] = {}
        for q in queries:
            for r in search(q):
                if r.url and r.url not in candidate_urls:
                    candidate_urls[r.url] = source_type_for(r.url)
        self.log(f"   {len(candidate_urls)} unique source URLs found.")

        # tool_name -> {evidence:[...], sources:[Source]}
        evidence: dict[str, dict] = defaultdict(lambda: {"evidence": [], "sources": []})
        for t in seeded:
            name = (t.get("name") or "").strip()
            if name:
                evidence[name]["evidence"].append(t)

        self.log("④ Visiting + screenshotting sources, extracting tools…")
        with Browser() as browser:
            urls = _prioritize(candidate_urls)[:MAX_DISCOVERY_PAGES]
            for idx, (url, stype) in enumerate(urls, 1):
                self.log(f"   [{idx}/{len(urls)}] ({stype}) {url}")
                cap = browser.capture(url, self.shots_dir, name_hint=_url_hint(url))
                if cap["error"]:
                    self.log(f"       ⚠ {cap['error'][:120]}")
                    continue
                found = self.llm.extract_tools_from_text(url, cap["title"], cap["text"])
                for tool in found:
                    name = (tool.get("name") or "").strip()
                    if not name:
                        continue
                    evidence[name]["evidence"].append(tool)
                    evidence[name]["sources"].append(
                        Source(
                            url=url,
                            title=cap["title"],
                            source_type=stype,
                            screenshot_path=cap["screenshot_path"],
                        )
                    )
                if found:
                    self.log(f"       + {len(found)} tool mention(s)")

            # Merge variant names.
            self.log("⑤ Canonicalizing tool names…")
            mapping = self.llm.canonicalize_names(list(evidence.keys()))
            merged: dict[str, dict] = defaultdict(lambda: {"evidence": [], "sources": []})
            for raw_name, bundle in evidence.items():
                canon = mapping.get(raw_name, raw_name).strip() or raw_name
                merged[canon]["evidence"].extend(bundle["evidence"])
                merged[canon]["sources"].extend(bundle["sources"])
            self.log(f"   {len(merged)} distinct tools after merge.")

            # Rank: prefer tools with more evidence/sources.
            ranked = sorted(
                merged.items(),
                key=lambda kv: (len(kv[1]["sources"]), len(kv[1]["evidence"])),
                reverse=True,
            )[: config.max_tools]

            self.log(f"⑥ Deep dive on top {len(ranked)} tools (official site capture)…")
            tools: list[Tool] = []
            for idx, (name, bundle) in enumerate(ranked, 1):
                self.log(f"   [{idx}/{len(ranked)}] {name}")
                record = self.llm.synthesize_tool(name, bundle["evidence"])
                tool = _record_to_tool(record, name)
                tool.sources = _dedup_sources(bundle["sources"])

                # Capture the official website if we have one and haven't already.
                site = tool.website
                if site and not any(_same_site(site, s.url) for s in tool.sources):
                    self.log(f"       ↳ capturing site {site}")
                    cap = browser.capture(site, self.shots_dir, name_hint=tool.slug)
                    if not cap["error"]:
                        tool.sources.insert(
                            0,
                            Source(
                                url=site,
                                title=cap["title"],
                                source_type="official",
                                screenshot_path=cap["screenshot_path"],
                            ),
                        )
                tools.append(tool)

        self.log("⑦ Writing catalog…")
        json_path = catalog.save_json(tools, self.run_dir)
        md_path = catalog.save_markdown(tools, self.run_dir)
        shots = sum(t.screenshot_count for t in tools)
        self.log(f"✅ Done · {len(tools)} tools · {shots} screenshots")
        self.log(f"   JSON: {json_path}")
        self.log(f"   Markdown: {md_path}")

        return {
            "run_dir": str(self.run_dir),
            "json": str(json_path),
            "markdown": str(md_path),
            "tool_count": len(tools),
            "screenshot_count": shots,
            "tools": [t.to_dict() for t in tools],
        }


# ----------------------------------------------------------------------
def _prioritize(candidate_urls: dict[str, str]) -> list[tuple[str, str]]:
    """Order URLs so we hit diverse, high-yield source types first."""
    order = {"review_site": 0, "blog": 1, "association": 2, "youtube": 3, "forum": 4, "other": 5}
    return sorted(candidate_urls.items(), key=lambda kv: order.get(kv[1], 9))


def _url_hint(url: str) -> str:
    from urllib.parse import urlparse

    return slugify(urlparse(url).netloc.replace("www.", ""))


def _record_to_tool(record: dict, fallback_name: str) -> Tool:
    return Tool(
        name=(record.get("name") or fallback_name).strip(),
        vendor=record.get("vendor", "") or "",
        website=record.get("website", "") or "",
        category=record.get("category", "") or "",
        description=record.get("description", "") or "",
        key_features=record.get("key_features", []) or [],
        pricing=record.get("pricing", "") or "",
        platforms=record.get("platforms", []) or [],
        confidence=record.get("confidence", "medium") or "medium",
    )


def _dedup_sources(sources: list[Source]) -> list[Source]:
    seen: set[str] = set()
    out: list[Source] = []
    for s in sources:
        if s.url in seen:
            continue
        seen.add(s.url)
        out.append(s)
    return out


def _same_site(a: str, b: str) -> bool:
    from urllib.parse import urlparse

    def host(u: str) -> str:
        return urlparse(u).netloc.replace("www.", "").lower()

    return bool(a) and bool(b) and host(a) == host(b)
