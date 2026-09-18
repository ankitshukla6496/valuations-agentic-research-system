# Valuations — Agentic Research System

An AI agent that scours the internet to **discover the software tools property &
asset valuation appraisers use** — and **captures screenshots of what those tools
look like**. It pulls from every source type it can reach: official product sites,
review sites (Capterra, G2, SoftwareAdvice, TrustRadius), YouTube demos & appraiser
vlogs, Reddit and appraiser forums, blogs, and industry associations.

It ships with a **web UI (Run button + live log + screenshot gallery)** and a CLI.

---

## What it produces

For each run, in `output/run-<timestamp>/`:

- `screenshots/` — full-page PNG screenshots of every source visited
- `CATALOG.md` — human-readable catalog (table + per-tool detail + inline screenshots)
- `catalog.json` — structured data: tool name, vendor, website, category, features,
  pricing, platforms, sources, and screenshot paths

Each tool record links back to the exact pages (and screenshots) it was found on.

---

## How it works

```
Seed topics
   │
   ├─▶ ① Claude plans ~20 diverse search queries (tools, reviews, YouTube, forums…)
   ├─▶ ② Claude lists tools it already knows (seed set)
   ├─▶ ③ Web search across all queries → candidate source URLs (classified by type)
   ├─▶ ④ Playwright visits + screenshots each source; Claude extracts tools mentioned
   ├─▶ ⑤ Claude canonicalizes/merges tool-name variants
   ├─▶ ⑥ Top tools: capture the official website + Claude synthesizes a clean record
   └─▶ ⑦ Write catalog.json + CATALOG.md
```

---

## Setup

Requires **Python 3.10+**.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # one-time: downloads the headless browser
cp .env.example .env                 # then add your ANTHROPIC_API_KEY
```

Search works **for free out of the box** via DuckDuckGo (`ddgs`) — no search key
needed. For higher-quality results set `SEARCH_PROVIDER=tavily` and a `TAVILY_API_KEY`.

### Required key
- `ANTHROPIC_API_KEY` — get one at <https://console.anthropic.com/settings/keys>

---

## Run it

### Web UI (recommended)
```bash
python webapp.py
```
Open <http://127.0.0.1:5000>, adjust the seed topics if you like, and click **▶ Run
research**. Watch the live log; when it finishes, browse the screenshot gallery.
Click any screenshot to enlarge it.

### CLI
```bash
python run.py                      # default seed topics
python run.py --seeds seeds.yaml   # your own seed topics
python run.py --max-tools 10       # smaller/faster run
```

---

## Configuration (`.env`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | **Required.** Claude API key. |
| `AGENT_MODEL` | `claude-sonnet-5` | Model for planning + extraction. `claude-opus-5` for depth, `claude-haiku-4-5-20251001` for speed. |
| `SEARCH_PROVIDER` | `ddgs` | `ddgs` (free) or `tavily` (needs key). |
| `TAVILY_API_KEY` | — | Only if using Tavily. |
| `MAX_TOOLS` | `25` | How many tools get a full deep-dive. |
| `RESULTS_PER_QUERY` | `8` | Search results pulled per query. |
| `HEADLESS` | `true` | Set `false` to watch the browser work. |
| `PAGE_TIMEOUT` | `30` | Per-page timeout (seconds). |

---

## Project layout

```
appraiser_agent/
  agent.py      # orchestrator (the pipeline above)
  llm.py        # Claude calls: planning, extraction, synthesis, dedup
  search.py     # ddgs / Tavily providers + source-type classification
  browser.py    # Playwright: screenshots + text capture
  catalog.py    # JSON + Markdown output
  models.py     # Tool / Source data models
  config.py     # env-driven settings
webapp.py       # Flask web UI (Run button, live log, gallery)
run.py          # CLI
templates/      # web UI template
seeds.yaml      # editable seed topics
```

---

## Notes & etiquette

- The agent reads publicly available pages and screenshots them for research.
  Respect each site's Terms of Service and `robots.txt`; use responsibly and at a
  reasonable rate.
- Screenshots and raw output are **git-ignored** by default (they can get large).
- Results are model-assisted; verify anything important against the linked sources.
