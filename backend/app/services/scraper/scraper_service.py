"""End-to-end scraping pipeline for a single URL.

    fetch → domain extractor → generic extractor → normalization

A failed fetch/extraction never raises into the caller database layer; it
returns a ``ScrapeOutcome`` that the worker turns into a failed ``ScrapeJob``
and a product status update — never into a snapshot or a price change.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.services.scraper.domains import get_extractor, is_known_domain, needs_js
from app.services.scraper.extractor import GenericExtractor, RawProduct
from app.services.scraper.fetcher import FetchError, fetch_html

logger = logging.getLogger("radar.scraper")


@dataclass
class ScrapeOutcome:
    success: bool
    raw: RawProduct | None = None
    error: str | None = None
    http_status: int | None = None
    used_js: bool = False
    duration_ms: int = 0
    domain_disabled: bool = False


def host_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0]


def is_domain_disabled(db: Session | None, host: str) -> bool:
    if db is None:
        return False
    from app.models import DomainState

    state = db.query(DomainState).filter(DomainState.domain == host).first()
    return bool(state and state.disabled)


def scrape_url(url: str, db: Session | None = None) -> ScrapeOutcome:
    """Scrape one product URL and return a normalized result.

    Never raises for network/store issues — those are captured in the outcome.
    """
    started = time.monotonic()
    host = host_of(url)

    if db is not None and is_domain_disabled(db, host):
        return ScrapeOutcome(
            success=False,
            error=f"le domaine {host} est temporairement désactivé",
            domain_disabled=True,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    extractor = get_extractor(host)
    use_js = bool(extractor and extractor.needs_js)

    try:
        html = fetch_html(url, use_js=use_js)
    except FetchError as exc:
        return ScrapeOutcome(
            success=False,
            error=str(exc),
            http_status=getattr(exc, "status", None),
            used_js=use_js,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    raw = RawProduct()

    if extractor is not None:
        try:
            raw = extractor.extract(html, url)
        except Exception as exc:  # domain extractor must never break the pipeline
            logger.warning("domain extractor %s failed: %s", host, exc, exc_info=True)
            raw = RawProduct()

    generic = GenericExtractor()
    try:
        generic_raw = generic.extract(html, url, currency_hint=raw.currency)
    except Exception as exc:
        logger.warning("generic extractor failed: %s", exc, exc_info=True)
        generic_raw = RawProduct()

    # Domain extractor wins when it found something; generic backs up the gaps.
    if extractor is not None:
        raw.merge(generic_raw)
    else:
        raw = generic_raw

    ok = raw.price is not None
    outcome = ScrapeOutcome(
        success=ok,
        raw=raw,
        error=None if ok else "prix non trouvé sur la page",
        used_js=use_js,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return outcome