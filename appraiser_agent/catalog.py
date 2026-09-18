"""Persistence + report generation for discovered tools."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Tool


def save_json(tools: list[Tool], out_dir: Path) -> Path:
    path = out_dir / "catalog.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_count": len(tools),
        "screenshot_count": sum(t.screenshot_count for t in tools),
        "tools": [t.to_dict() for t in tools],
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def save_markdown(tools: list[Tool], out_dir: Path) -> Path:
    path = out_dir / "CATALOG.md"
    lines: list[str] = [
        "# Valuation Appraiser Tools — Catalog",
        "",
        f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}_",
        f"_{len(tools)} tools · {sum(t.screenshot_count for t in tools)} screenshots_",
        "",
        "| Tool | Category | Platforms | Screenshots | Confidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for t in sorted(tools, key=lambda x: x.name.lower()):
        lines.append(
            f"| [{t.name}](#{t.slug}) | {t.category or '—'} | "
            f"{', '.join(t.platforms) or '—'} | {t.screenshot_count} | {t.confidence} |"
        )
    lines.append("")

    for t in sorted(tools, key=lambda x: x.name.lower()):
        lines += [
            f"## {t.name}",
            f'<a name="{t.slug}"></a>',
            "",
            f"- **Vendor:** {t.vendor or '—'}",
            f"- **Website:** {t.website or '—'}",
            f"- **Category:** {t.category or '—'}",
            f"- **Platforms:** {', '.join(t.platforms) or '—'}",
            f"- **Pricing:** {t.pricing or '—'}",
            f"- **Confidence:** {t.confidence}",
            "",
            t.description or "_No description gathered._",
            "",
        ]
        if t.key_features:
            lines.append("**Key features:**")
            lines += [f"- {f}" for f in t.key_features]
            lines.append("")
        if t.sources:
            lines.append("**Sources & screenshots:**")
            for s in t.sources:
                shot = ""
                if s.screenshot_path:
                    rel = Path(s.screenshot_path).relative_to(out_dir) if _under(s.screenshot_path, out_dir) else s.screenshot_path
                    shot = f" — ![shot]({rel})"
                lines.append(f"- [{s.source_type}] [{s.title or s.url}]({s.url}){shot}")
            lines.append("")
        lines.append("---\n")

    path.write_text("\n".join(lines))
    return path


def _under(path_str: str, parent: Path) -> bool:
    try:
        Path(path_str).relative_to(parent)
        return True
    except ValueError:
        return False
