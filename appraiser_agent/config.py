"""Central configuration, loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass
class Config:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    agent_model: str = field(default_factory=lambda: os.getenv("AGENT_MODEL", "claude-sonnet-5"))

    search_provider: str = field(default_factory=lambda: os.getenv("SEARCH_PROVIDER", "ddgs").lower())
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))

    max_tools: int = field(default_factory=lambda: _get_int("MAX_TOOLS", 25))
    results_per_query: int = field(default_factory=lambda: _get_int("RESULTS_PER_QUERY", 8))
    headless: bool = field(default_factory=lambda: _get_bool("HEADLESS", True))
    page_timeout: int = field(default_factory=lambda: _get_int("PAGE_TIMEOUT", 30))

    output_dir: Path = OUTPUT_DIR

    def validate(self) -> None:
        if not self.anthropic_api_key:
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        if self.search_provider == "tavily" and not self.tavily_api_key:
            raise SystemExit(
                "SEARCH_PROVIDER=tavily but TAVILY_API_KEY is not set. "
                "Add the key or set SEARCH_PROVIDER=ddgs (free)."
            )


config = Config()
