"""Data models for discovered tools and captured sources."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "unknown"


@dataclass
class Source:
    """A single web page / video that was visited and (usually) screenshotted."""

    url: str
    title: str = ""
    # official | review_site | youtube | forum | blog | association | other
    source_type: str = "other"
    screenshot_path: str = ""
    downloaded_images: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Tool:
    """A software tool valuation appraisers use."""

    name: str
    slug: str = ""
    vendor: str = ""
    website: str = ""
    category: str = ""          # e.g. "URAR form-filling", "comps/analytics", "workflow"
    description: str = ""
    key_features: list[str] = field(default_factory=list)
    pricing: str = ""
    platforms: list[str] = field(default_factory=list)  # web, desktop, iOS, Android
    sources: list[Source] = field(default_factory=list)
    confidence: str = "medium"  # low | medium | high

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = slugify(self.name)

    @property
    def screenshot_count(self) -> int:
        return sum(1 for s in self.sources if s.screenshot_path)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["screenshot_count"] = self.screenshot_count
        return data
