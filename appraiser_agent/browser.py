"""Playwright-based page capture: full-page screenshots + text + notable images."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

from .config import config
from .models import slugify

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class Browser:
    """Thin wrapper around a persistent Playwright browser context."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self) -> "Browser":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=config.headless)
        self._context = self._browser.new_context(
            user_agent=_UA,
            viewport={"width": 1440, "height": 900},
        )
        self._context.set_default_timeout(config.page_timeout * 1000)
        return self

    def __exit__(self, *exc) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer:
                    closer.close()
            except Exception:  # noqa: BLE001
                pass
        if self._pw:
            self._pw.stop()

    def capture(self, url: str, screenshot_dir: Path, name_hint: str = "") -> dict:
        """Visit `url`; return {title, text, screenshot_path, images:[...] , error}."""
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        result = {"title": "", "text": "", "screenshot_path": "", "images": [], "error": ""}
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:  # noqa: BLE001 — networkidle is best-effort
                pass
            _dismiss_cookies(page)
            result["title"] = (page.title() or "")[:300]

            base = slugify(name_hint or urlparse(url).netloc or "page")
            shot = screenshot_dir / f"{base}.png"
            i = 1
            while shot.exists():
                i += 1
                shot = screenshot_dir / f"{base}-{i}.png"
            page.screenshot(path=str(shot), full_page=True)
            result["screenshot_path"] = str(shot)

            try:
                result["text"] = page.evaluate("() => document.body.innerText")[:20000]
            except Exception:  # noqa: BLE001
                result["text"] = ""
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
        finally:
            page.close()
        return result


@contextmanager
def browser_session():
    with Browser() as b:
        yield b


def _dismiss_cookies(page) -> None:
    """Best-effort: click an obvious accept/close button so shots aren't covered."""
    selectors = [
        "button:has-text('Accept')",
        "button:has-text('Accept all')",
        "button:has-text('I agree')",
        "button:has-text('Got it')",
        "#onetrust-accept-btn-handler",
        "[aria-label='Close']",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=1500)
                page.wait_for_timeout(400)
                return
        except Exception:  # noqa: BLE001
            continue
