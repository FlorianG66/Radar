"""Extraction of product data from a fetched HTML page.

Architecture:
    Scraper
     → GenericExtractor (JSON-LD, microdata, Open Graph, heuristic selectors)
     → DomainExtractor (registered per domain, fills/overrides gaps)
     → ProductNormalizer (pricetext.normalize_price)

The rendering step (Playwright) is handled one level up in ``fetcher`` and is
only used when the domain's extractor declares ``needs_js = True``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from app.services.scraper.pricetext import normalize_price, parse_number

SKIP_JSONLD_TYPES = {"BreadcrumbList", "WebSite", "Organization", "WebPage", "FAQPage", "VideoObject"}

PRICE_SELECTORS = [
    '[itemprop="price"]',
    "meta[itemprop='price']",
    '[class*="price"]',
    "[class*='Price']",
    ".price",
    "#price",
    "[data-testid*='price']",
    "[data-price]",
]

OUT_OF_STOCK_TEXTS = [
    "rupture de stock",
    "rupu de stock",
    "épuisé",
    "en rupture",
    "sold out",
    "out of stock",
    "indisponible",
    "nicht verfügbar",
    "erschöpft",
    "agotado",
    "esaurito",
]

PROMO_TEXTS = ["promo", "promotion", "sale", "en solde", "réduit", "reduced", "rabais", "discount", "-%", "offerte"]
IN_STOCK_TEXTS = ["ajouter au panier", "add to cart", "in stock", "en stock", "disponible", "acheter"]

_PROMO_MULTI_RE = re.compile(r"(\d+)\s*%")
_PROMO_NUMBER_RE = re.compile(r"-(\d+,\d+|\d+\.\d+|\d+)", re.IGNORECASE)


@dataclass
class RawProduct:
    name: str | None = None
    price: float | None = None
    original_price: str | None = None
    currency: str | None = None
    previous_price: float | None = None
    original_previous_price: str | None = None
    availability: str | None = None  # in_stock | out_of_stock | preorder
    stock_quantity: int | None = None
    in_promotion: bool = False
    shipping_cost: float | None = None
    sku: str | None = None
    ean: str | None = None
    image_url: str | None = None
    extras: dict = field(default_factory=dict)

    def merge(self, other: "RawProduct") -> None:
        """Fill missing fields from ``other`` (lower priority)."""
        for f in self.__dataclass_fields__:
            cur = getattr(self, f)
            if cur in (None, "", False) and f != "in_promotion":
                setattr(self, f, getattr(other, f))
            elif f == "in_promotion" and not cur:
                self.in_promotion = other.in_promotion


def _json_text(doc: BeautifulSoup) -> str:
    return doc.get_text(" ", strip=True)


def _price_value(node: Tag, currency_hint: str | None) -> tuple[float | None, str | None]:
    """Try a price from a JSON-LD offer/node"""
    text = None
    if isinstance(node, dict):
        for key in ("price", "lowPrice", "highPrice"):
            if key in node:
                text = str(node[key])
                break
    else:
        for key in ("content", "value", "data-price"):
            if node.has_attr(key):
                text = node[key]
                break
        if text is None:
            text = node.get_text(" ", strip=True)
    if text is None or text == "":
        return None, None
    return normalize_price(text, currency_hint)


class GenericExtractor:
    """Robust extraction that works across most e-commerce pages."""

    def extract(self, html: str, url: str, currency_hint: str | None = None) -> RawProduct:
        soup = BeautifulSoup(html, "lxml")
        product = RawProduct()

        self._extract_json_ld(soup, product, currency_hint)
        json_ld_had_price = product.price is not None

        if product.price is None:
            self._extract_microdata(soup, product, currency_hint)
        if product.price is None:
            self._extract_open_graph(soup, url, product, currency_hint)
        if product.price is None or product.name is None:
            self._extract_heuristics(soup, url, product, currency_hint)

        if product.price is None:
            self._extract_json_ld(soup, product, currency_hint, only_price=True)

        self._availability_heuristics(soup, product)
        self._promotion_heuristics(soup, product)
        if product.ean is None:
            product.ean = self._extract_ean(soup, product.sku or "")
        return product

    # --- JSON-LD ---
    def _extract_json_ld(self, soup: BeautifulSoup, product: RawProduct, currency_hint: str | None, only_price: bool = False) -> None:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, AttributeError):
                continue
            for item in self._iter_jsonld_nodes(data):
                if isinstance(item, dict) and item.get("@type") in SKIP_JSONLD_TYPES:
                    continue
                if isinstance(item, dict) and self._looks_like_product(item):
                    self._fill_jsonld_item(item, product, currency_hint, only_price)
                    if product.price is not None:
                        return
                offers = isinstance(item, dict) and item.get("offers")
                if offers:
                    broad = offers if isinstance(offers, list) else [offers]
                    for offer in broad:
                        if isinstance(offer, dict):
                            self._fill_jsonld_offer(offer, product, currency_hint)

    def _iter_jsonld_nodes(self, data):
        if isinstance(data, dict):
            yield data
            for v in data.values():
                yield from self._iter_jsonld_nodes(v)
        elif isinstance(data, list):
            for v in data:
                yield from self._iter_jsonld_nodes(v)

    def _looks_like_product(self, node: dict) -> bool:
        t = node.get("@type")
        if isinstance(t, list):
            return any("Product" in str(x) or "Offer" in str(x) for x in t)
        return t is not None and ("Product" in str(t) or str(t) == "ItemList")

    def _fill_jsonld_item(self, node: dict, product: RawProduct, currency_hint: str | None, only_price: bool) -> None:
        if not only_price and product.name is None:
            name = node.get("name")
            if name:
                product.name = str(name)[:255]
        if not only_price and product.image_url is None:
            img = node.get("image")
            if isinstance(img, list) and img:
                img = img[0]
            if isinstance(img, dict):
                img = img.get("url")
            if img:
                product.image_url = str(img)
        if not only_price:
            for k in ("sku", "mpn", "gtin13", "gtin", "ean"):
                if k in node and node[k] and product.ean is None and "gtin" in k.lower():
                    product.ean = str(node[k])
                elif k in node and node[k] and product.sku is None and k in ("sku", "mpn"):
                    product.sku = str(node[k])
        offers = node.get("offers")
        if offers:
            broad = offers if isinstance(offers, list) else [offers]
            for offer in broad:
                if isinstance(offer, dict):
                    self._fill_jsonld_offer(offer, product, currency_hint)

    def _fill_jsonld_offer(self, offer: dict, product: RawProduct, currency_hint: str | None) -> None:
        if product.price is not None:
            return
        price, currency = _price_value(offer, currency_hint)
        if price is None:
            return
        product.price = price
        product.currency = currency
        product.original_price = str(offer.get("price", ""))[:64] or None
        availability = offer.get("availability", "")
        if availability:
            product.availability = self._map_availability(str(availability))
        if "priceCurrency" in offer and isinstance(offer["priceCurrency"], str):
            product.currency = offer["priceCurrency"].upper()[:3]

    # --- Microdata ---
    def _extract_microdata(self, soup: BeautifulSoup, product: RawProduct, currency_hint: str | None) -> None:
        node = soup.find(itemprop="price")
        if node:
            price, currency = _price_value(node, currency_hint)
            product.price, product.currency = price, currency or product.currency
            txt = node.get("content") or node.get_text(" ", strip=True)
            if txt:
                product.original_price = str(txt)[:64]
        name = soup.find(itemprop="name")
        if name and product.name is None:
            product.name = name.get_text(" ", strip=True)[:255] or None
        av = soup.find(itemprop="availability")
        if av and product.availability is None:
            product.availability = self._map_availability(av.get("href") or av.get_text(" ", strip=True) or "")
        for prop in ("sku", "mpn"):
            el = soup.find(itemprop=prop)
            if el and product.sku is None:
                product.sku = el.get("content") or el.get_text(" ", strip=True)[:128]
        img = soup.find(itemprop="image")
        if img:
            content = img.get("content")
            if content:
                product.image_url = str(content)

    # --- Open Graph / meta ---
    def _extract_open_graph(self, soup: BeautifulSoup, url: str, product: RawProduct, currency_hint: str | None) -> None:
        def meta(prop: str) -> str | None:
            el = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
            return el.get("content") if el else None

        if product.name is None:
            title = meta("og:title") or meta("twitter:title") or soup.title.get_text(" ", strip=True) if soup.title else None
            if title:
                product.name = str(title)[:255]
        if product.price is None:
            amount = meta("product:price:amount") or meta("og:price:amount") or meta("twitter:data1")
            if amount:
                price, currency = normalize_price(str(amount), currency_hint)
                if price is not None:
                    product.price, product.currency = price, currency
                    product.original_price = str(amount)[:64]
                    if product.currency is None:
                        product.currency = (meta("product:price:currency") or meta("og:price:currency") or currency_hint) or None
        if product.image_url is None:
            img = meta("og:image")
            if img:
                product.image_url = urljoin(url, img)

    # --- Heuristic selectors ---
    def _extract_heuristics(self, soup: BeautifulSoup, url: str, product: RawProduct, currency_hint: str | None) -> None:
        if product.name is None and soup.title:
            title = soup.title.get_text(" ", strip=True)
            if title:
                normalized = re.sub(r"\s*[|\-–]\s*(Amazon|FNAC|Darty|Media Markt|Boulanger|LDLC|Amazon\.fr|.*\.com).*$", "", title, flags=re.IGNORECASE)
                product.name = normalized.strip()[:255] or None
        if product.price is None:
            # Collect all plausible price candidates; the current price is
            # (heuristically) the lowest one. Strike-through values are higher
            # and are later captured as the "old" price by promotion heuristics.
            candidates: list[tuple[float, str, str | None]] = []
            seen: set[float] = set()
            for sel in PRICE_SELECTORS:
                for node in soup.select(sel):
                    price, currency = _price_value(node, currency_hint)
                    if price is not None and 0 < price < 10_000_000 and price not in seen:
                        seen.add(price)
                        candidates.append((price, node.get_text(" ", strip=True)[:64], currency))
            if candidates:
                price, text, currency = min(candidates, key=lambda c: c[0])
                product.price = price
                if currency:
                    product.currency = currency
                product.original_price = text

    # --- Availability & promotion ---
    def _map_availability(self, raw: str) -> str:
        low = raw.lower()
        if any(k in low for k in ("outofstock", "out_of_stock", "soldout", "sold_out", "oos", "rupture", "epuise", "épuisé", "preorder", "preorder")):
            return "preorder" if "preorder" in low else "out_of_stock"
        if any(k in low for k in ("instock", "in_stock", "in_stock", "en stock", "disponible", "in stock")):
            return "in_stock"
        return "in_stock" if low == "in stock" else None

    def _availability_heuristics(self, soup: BeautifulSoup, product: RawProduct) -> None:
        if product.availability is not None:
            return
        text = _json_text(soup)
        low = text.lower()
        if any(key in low for key in OUT_OF_STOCK_TEXTS):
            if "précommande" in low or "preorder" in low:
                product.availability = "preorder"
            else:
                product.availability = "out_of_stock"
        else:
            # If there is any stock-related signal we assume in stock.
            if any(key in low for key in IN_STOCK_TEXTS) or soup.find(id=re.compile("add.*cart", re.I)) or soup.find(class_=re.compile("add.*cart", re.I)):
                product.availability = "in_stock"

    def _promotion_heuristics(self, soup: BeautifulSoup, product: RawProduct) -> None:
        if product.in_promotion:
            return
        text = _json_text(soup)
        low = text.lower()
        # striker-through price signal
        prev = None
        for node in soup.select("[class*='old'], [class*='was'], [class*='previous'], s, del, [class*='before']"):
            val = parse_number(node.get_text(" ", strip=True))
            if val and product.price and val > product.price:
                prev = val
                product.original_previous_price = node.get_text(" ", strip=True)[:64]
                break
        product.previous_price = prev
        product.in_promotion = prev is not None or any(key in low for key in PROMO_TEXTS)
        if not product.in_promotion and product.price:
            m = _PROMO_MULTI_RE.search(text)
            product.in_promotion = m is not None

    def _extract_ean(self, soup: BeautifulSoup, sku: str) -> str | None:
        for tag in soup.find_all(string=re.compile(r"\b(\d{13})\b")):
            num = re.search(r"\b(\d{13})\b", tag)
            if num and num.group(1)[:2] in ("30", "33", "34", "36", "37"):
                return num.group(1)
        return None


class DomainExtractor:
    """Base class for store-specific extractors."""

    domains: tuple[str, ...] = ()
    needs_js: bool = False

    def extract(self, html: str, url: str) -> RawProduct:
        raise NotImplementedError

    @staticmethod
    def host_of(url: str) -> str:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host.split(":")[0]