#!/usr/bin/env python3
"""CLI entrypoint.

Usage:
    python run.py                       # run with default seed topics
    python run.py --seeds seeds.yaml    # run with custom seed topics
    python run.py --max-tools 10        # override how many tools to deep-dive
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from rich.console import Console

from appraiser_agent.agent import Agent
from appraiser_agent.config import config

console = Console()


def load_seeds(path: str | None) -> list[str] | None:
    if not path:
        return None
    data = yaml.safe_load(Path(path).read_text())
    if isinstance(data, dict):
        return data.get("seeds", [])
    return list(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Valuations — Agentic Research System")
    parser.add_argument("--seeds", help="Path to a YAML file with a `seeds:` list.")
    parser.add_argument("--max-tools", type=int, help="Override MAX_TOOLS for this run.")
    args = parser.parse_args()

    if args.max_tools:
        config.max_tools = args.max_tools

    seeds = load_seeds(args.seeds)
    agent = Agent(seeds=seeds, progress=lambda m: console.print(m))
    result = agent.run()

    console.rule("[bold green]Summary")
    console.print(f"Tools discovered : [bold]{result['tool_count']}[/]")
    console.print(f"Screenshots      : [bold]{result['screenshot_count']}[/]")
    console.print(f"Catalog (md)     : {result['markdown']}")
    console.print(f"Catalog (json)   : {result['json']}")


if __name__ == "__main__":
    main()
