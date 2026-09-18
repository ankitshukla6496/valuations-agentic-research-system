"""Claude wrapper: planning, tool extraction, and synthesis.

All calls return parsed JSON. We keep prompts tight and ask for strict JSON so
the agent stays deterministic and easy to debug.
"""
from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic

from .config import config


class LLM:
    def __init__(self) -> None:
        self.client = Anthropic(api_key=config.anthropic_api_key)
        self.model = config.agent_model

    def _json_call(self, system: str, user: str, max_tokens: int = 2000) -> Any:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text").strip()
        return _extract_json(text)

    # --- Planning -------------------------------------------------------
    def plan_search_queries(self, seed_topics: list[str]) -> list[str]:
        """Turn seed topics into a diverse set of web search queries.

        Deliberately spans many source types: official product pages, review
        sites, YouTube demos/vlogs, forums, blogs, and associations.
        """
        system = (
            "You are a research planner mapping the software tools that property "
            "and asset VALUATION APPRAISERS use in their daily work. Produce web "
            "search queries that will surface tools AND what they look like."
        )
        user = f"""Seed topics:
{json.dumps(seed_topics, indent=2)}

Generate 18-25 varied search queries. Cover these angles explicitly:
- named appraisal/valuation software and vendors
- "best appraisal software" style roundups and review sites (Capterra, G2, SoftwareAdvice, TrustRadius)
- YouTube demos, tutorials, and appraiser vlogs showing software on screen
- Reddit and appraiser forums (e.g. appraisersforum) discussing tools
- form-filling (URAR/UAD), comps/analytics, inspection/mobile, workflow/CRM tools
- screenshots / UI / "what does X look like"

Return STRICT JSON: {{"queries": ["...", "..."]}}"""
        data = self._json_call(system, user, max_tokens=1500)
        return list(dict.fromkeys(data.get("queries", [])))  # dedup, keep order

    def known_tools(self, seed_topics: list[str]) -> list[dict[str, str]]:
        """Seed the run with tools the model already knows about."""
        system = (
            "You are an expert on the property/asset valuation & appraisal software "
            "market. List real, currently-known tools appraisers use."
        )
        user = f"""Context / focus: {json.dumps(seed_topics)}

List up to 30 real software tools valuation appraisers use. For each give a best-guess
official website (or empty string if unsure) and a short category.

Return STRICT JSON:
{{"tools": [{{"name": "...", "website": "...", "category": "...", "vendor": "..."}}]}}"""
        data = self._json_call(system, user, max_tokens=2500)
        return data.get("tools", [])

    # --- Extraction -----------------------------------------------------
    def extract_tools_from_text(self, url: str, title: str, text: str) -> list[dict[str, Any]]:
        """From one page's text, pull any valuation tools mentioned."""
        system = (
            "You extract software tool names for VALUATION/APPRAISAL professionals "
            "from web page text. Only include actual named software products/tools."
        )
        user = f"""Page URL: {url}
Page title: {title}

Page text (truncated):
\"\"\"
{text[:8000]}
\"\"\"

Extract tools relevant to property/asset valuation appraisers. For each provide any
details visible in the text.

Return STRICT JSON:
{{"tools": [{{"name": "...", "vendor": "...", "website": "...", "category": "...",
"description": "...", "key_features": ["..."], "pricing": "...",
"platforms": ["web|desktop|iOS|Android"]}}]}}
If none, return {{"tools": []}}."""
        data = self._json_call(system, user, max_tokens=2500)
        return data.get("tools", [])

    def synthesize_tool(self, name: str, evidence: list[dict[str, str]]) -> dict[str, Any]:
        """Merge everything gathered about one tool into a clean record."""
        system = (
            "You consolidate research notes about a single valuation/appraisal "
            "software tool into one accurate, non-duplicative record."
        )
        user = f"""Tool name: {name}

Collected evidence (from multiple pages):
{json.dumps(evidence, indent=2)[:12000]}

Consolidate into one record. Deduplicate features. Keep it factual; if a field is
unknown leave it empty. Set confidence low|medium|high based on evidence quality.

Return STRICT JSON:
{{"name": "...", "vendor": "...", "website": "...", "category": "...",
"description": "...", "key_features": ["..."], "pricing": "...",
"platforms": ["..."], "confidence": "low|medium|high"}}"""
        return self._json_call(system, user, max_tokens=2000)

    def canonicalize_names(self, names: list[str]) -> dict[str, str]:
        """Map messy/variant tool names to a canonical name for dedup."""
        if not names:
            return {}
        system = "You normalize software product names so variants map to one canonical name."
        user = f"""Names found:
{json.dumps(names, indent=2)}

Return STRICT JSON mapping each input name to its canonical name (merge obvious
duplicates / variants, e.g. "TOTAL by a la mode" and "a la mode TOTAL"):
{{"mapping": {{"input name": "Canonical Name"}}}}"""
        data = self._json_call(system, user, max_tokens=2000)
        return data.get("mapping", {})


def _extract_json(text: str) -> Any:
    """Best-effort JSON extraction from a model response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Grab the outermost {...} or [...]
        for open_c, close_c in (("{", "}"), ("[", "]")):
            start = text.find(open_c)
            end = text.rfind(close_c)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
    return {}
