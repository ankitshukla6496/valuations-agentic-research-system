#!/usr/bin/env python3
"""Local web UI: a Run button, a live progress log, and a screenshot gallery.

    python webapp.py     # then open http://127.0.0.1:5000

The agent runs in a background thread. Progress is streamed to the browser via
Server-Sent Events. When it finishes, the page renders the catalog with each
tool's screenshots (served from output/).
"""
from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from appraiser_agent.agent import Agent
from appraiser_agent.config import config

app = Flask(__name__)


@app.before_request
def _handle_preflight():
    # Allow the Vercel-hosted frontend (different origin) to call this API.
    if request.method == "OPTIONS":
        return ("", 204)


@app.after_request
def _add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

# --- shared run state -------------------------------------------------
_state = {
    "running": False,
    "log": [],            # list[str]
    "result": None,       # dict from Agent.run()
    "error": None,
}
_events: "queue.Queue[str]" = queue.Queue()
_lock = threading.Lock()


def _emit(msg: str) -> None:
    with _lock:
        _state["log"].append(msg)
    _events.put(msg)


def _run_agent(seeds: list[str] | None, max_tools: int | None) -> None:
    try:
        if max_tools:
            config.max_tools = max_tools
        agent = Agent(seeds=seeds, progress=_emit)
        result = agent.run()
        with _lock:
            _state["result"] = result
    except SystemExit as exc:  # missing key etc.
        with _lock:
            _state["error"] = str(exc)
        _emit(f"❌ {exc}")
    except Exception as exc:  # noqa: BLE001
        with _lock:
            _state["error"] = str(exc)
        _emit(f"❌ Error: {exc}")
    finally:
        with _lock:
            _state["running"] = False
        _events.put("__DONE__")


@app.route("/")
def index():
    return render_template("index.html", max_tools=config.max_tools)


@app.route("/start", methods=["POST"])
def start():
    with _lock:
        if _state["running"]:
            return jsonify({"ok": False, "error": "A run is already in progress."}), 409
        _state.update(running=True, log=[], result=None, error=None)
    payload = request.get_json(silent=True) or {}
    raw_seeds = (payload.get("seeds") or "").strip()
    seeds = [s.strip() for s in raw_seeds.splitlines() if s.strip()] or None
    max_tools = payload.get("max_tools")
    threading.Thread(target=_run_agent, args=(seeds, max_tools), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/stream")
def stream():
    def gen():
        # Replay any log lines already collected (in case of reconnect).
        with _lock:
            backlog = list(_state["log"])
        for line in backlog:
            yield f"data: {json.dumps({'line': line})}\n\n"
        while True:
            msg = _events.get()
            if msg == "__DONE__":
                yield f"data: {json.dumps({'done': True})}\n\n"
                break
            yield f"data: {json.dumps({'line': msg})}\n\n"

    return Response(gen(), mimetype="text/event-stream")


@app.route("/result")
def result():
    with _lock:
        return jsonify({
            "running": _state["running"],
            "result": _state["result"],
            "error": _state["error"],
        })


@app.route("/shots/<path:relpath>")
def shots(relpath: str):
    """Serve screenshots from output/ so the gallery can display them."""
    return send_from_directory(config.output_dir, relpath)


if __name__ == "__main__":
    import os

    config.output_dir.mkdir(parents=True, exist_ok=True)
    # Local dev server. In production, gunicorn imports `app` (see Dockerfile).
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")
    print(f"Open http://{host}:{port}")
    app.run(host=host, port=port, threaded=True, debug=False)
