"""Search a product by name across a catalog of merchants.

Discovery is done in two phases:

1. find candidate product URLs on a merchant via its own search endpoint
   (the bundled demo shop) or a site-restricted web search (DuckDuckGo) for
   real merchants;
2. scrape the top candidates with the standard pipeline
   (``scrape_url``) so each result carries a name and a current price.

Every merchant is independent: an unreachable or blocked merchant simply
reports an error and never breaks the search for the others.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, quote, urljoin, urlparse, urlsplit

from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.services.scraper.fetcher import FetchError, fetch_html
from app.services.scraper.scraper_service import scrape_url

logger = logging.getLogger("radar.search")

# Curated French merchants searched by default (label, domain).
# Best effort: a merchant that blocks or throttles us is simply skipped.
MERCHANTS = [
    ("Fnac", "fnac.com"),
    ("Darty", "darty.com"),
    ("LDLC", "ldlc.com"),
    ("Cdiscount", "cdiscount.com"),
    ("Boulanger", "boulanger.com"),
    ("Rue du Commerce", "rueducommerce.fr"),
    ("Amazon", "amazon.fr"),
]

DEMO_HOSTS = ("localhost", "127.0.0.1", "demo.radar.local", "radar-demo.internal")

# Soft caps so an interactive search stays responsive.
MAX_MERCHANTS = 8
MAX_CANDIDATES_PER_MERCHANT = 4


@dataclass
class SearchResult:
    domain: str
    label: str
    name: str
    url: str
    price: float | None = None
    currency: str | None = None
    availability: str | None = None
    image_url: str | None = None


@dataclass
class MerchantStatus:
    domain: str
    label: str
    ok: bool
    error: str | None = None


@dataclass
class SearchOutcome:
    query: str
    merchants: list[MerchantStatus] = field(default_factory=list)
    results: list[SearchResult] = field(default_factory=list)


def _host_of(url: str) -> str:
    s = url.strip()
    if "://" not in s:
        s = "http://" + s
    host = (urlparse(s).netloc or s).lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0]


class BaseSearchProvider:
    """Finds candidate product URLs for a ``terms`` query on ``host``."""

    def discover(self, terms: str, host: str) -> list[str]:
        raise NotImplementedError


class DemoShopSearchProvider(BaseSearchProvider):
    """Searches the bundled demo shop (deterministic, offline)."""

    def discover(self, terms: str, host: str) -> list[str]:
        if host in ("localhost", "127.0.0.1"):
            base = get_settings().DEMO_SHOP_URL.rstrip("/")
        else:
            base = f"http://{host}"
        html = fetch_html(f"{base}/search?q={quote(terms)}")
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        for a in soup.select("a[data-radar='result']"):
            href = a.get("href")
            if href:
                urls.append(urljoin(base + "/", href))
        return urls


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """Site-restricted web search for real merchants."""

    def discover(self, terms: str, host: str) -> list[str]:
        query = quote(f"{terms} site:{host}")
        html = fetch_html(f"https://html.duckduckgo.com/html/?q={query}")
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        for a in soup.select("a.result__a"):
            href = a.get("href") or ""
            if "uddg=" in href:
                href = parse_qs(urlsplit(href).query).get("uddg", [href])[0]
            if _host_of(href) in (host, f"www.{host}"):
                urls.append(href)
        return urls


def provider_for(host: str) -> BaseSearchProvider:
    if host in DEMO_HOSTS:
        return DemoShopSearchProvider()
    return DuckDuckGoSearchProvider()


def search_products(query: str, merchants: list[tuple[str, str]]) -> SearchOutcome:
    """Search ``query`` across ``merchants`` (label, domain) pairs."""
    outcome = SearchOutcome(query=query)

    seen: set[str] = set()
    for label, domain in merchants:
        host = _host_of(domain)
        if not host or host in seen:
            continue
        seen.add(host)
        if len(seen) > MAX_MERCHANTS:
            break

        try:
            candidates = provider_for(host).discover(query, host)
        except FetchError as exc:
            outcome.merchants.append(MerchantStatus(host, label, ok=False, error=str(exc)))
            logger.info("search discover failed for %s: %s", host, exc)
            continue

        result: SearchResult | None = None
        for url in candidates[:MAX_CANDIDATES_PER_MERCHANT]:
            sc = scrape_url(url)
            if sc.success and sc.raw is not None and sc.raw.price is not None:
                raw = sc.raw
                result = SearchResult(
                    domain=host,
                    label=label,
                    name=(raw.name or query)[:255],
                    url=url,
                    price=float(raw.price),
                    currency=raw.currency,
                    availability=raw.availability,
                    image_url=raw.image_url,
                )
                break

        outcome.merchants.append(MerchantStatus(host, label, ok=True, error=None))
        if result is not None:
            outcome.results.append(result)

    outcome.results.sort(key=lambda r: -_similarity(r.name, query))
    return outcome


def _tokens(text: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9]+", " ", text.lower()).split() if len(w) > 1}


def _similarity(name: str, query: str) -> float:
    """Rough relevance: query-token coverage + bonus when query is contained."""
    name_tokens = _tokens(name)
    query_tokens = _tokens(query)
    if not query_tokens:
        return 1.0
    coverage = len(name_tokens & query_tokens) / len(query_tokens)
    bonus = 0.5 if query.strip().lower() in name.lower() else 0.0
    return coverage + bonus