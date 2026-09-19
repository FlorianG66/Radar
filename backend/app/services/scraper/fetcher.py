"""HTTP / JS-rendering layer for scrapers.

Chooses the cheapest reliable path:
- plain HTTP (httpx) by default;
- headless rendering (Playwright) only for domains that declare
  ``needs_js = True`` in their extractor.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger("radar.scraper.fetcher")

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


class FetchError(Exception):
    def __init__(self, message: str, status: int | None = None, retryable: bool = True):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


def fetch_html(url: str, use_js: bool = False) -> str:
    """Return the rendered HTML of ``url``."""
    settings = get_settings()
    if use_js:
        return _fetch_with_playwright(url)
    try:
        with httpx.Client(timeout=settings.SCRAPE_TIMEOUT_SECONDS, follow_redirects=True, headers=DEFAULT_HEADERS) as client:
            resp = client.get(url)
        if resp.status_code >= 400:
            raise FetchError(f"HTTP {resp.status_code}", status=resp.status_code, retryable=resp.status_code >= 500)
        return resp.text
    except httpx.TimeoutException as exc:
        raise FetchError("timeout", retryable=True) from exc
    except httpx.TransportError as exc:
        raise FetchError(f"network error: {exc.__class__.__name__}", retryable=True) from exc


def _fetch_with_playwright(url: str) -> str:
    """Render a page with a headless browser. Players gracefully when Playwright
    is not installed (falls back to plain HTTP) so local dev keeps working."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright not installed, falling back to HTTP fetch for %s", url)
        return fetch_html(url, use_js=False)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])
            page.goto(url, timeout=get_settings().SCRAPE_TIMEOUT_SECONDS * 1000, wait_until="networkidle")
            html = page.content()
            browser.close()
            return html
    except asyncio.TimeoutError as exc:
        raise FetchError("playwright timeout", retryable=True) from exc
    except Exception as exc:  # pragma: no cover - browser launchers vary
        raise FetchError(f"playwright error: {exc.__class__.__name__}", retryable=True) from exc