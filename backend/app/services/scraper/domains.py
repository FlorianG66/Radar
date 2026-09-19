"""Domain-specific extractors.

Add a new store by subclassing ``DomainExtractor`` and decorating it with
``@register_domain``. The registry maps hostname → extractor, so adding a
new domain never touches the core pipeline.

The ``DemoShopExtractor`` powers the bundled demo shop (fixtures + a tiny
demo site) so that automated tests never depend on an external website.
"""
from __future__ import annotations

import json

from bs4 import BeautifulSoup

from app.services.scraper.extractor import DomainExtractor, RawProduct, _price_value

REGISTRY: dict[str, DomainExtractor] = {}


def register_domain(cls: type[DomainExtractor]) -> type[DomainExtractor]:
    instance = cls()
    for domain in cls.domains:
        REGISTRY[domain] = instance
    return cls


def get_extractor(host: str) -> DomainExtractor | None:
    return REGISTRY.get(host)


def needs_js(host: str) -> bool:
    extractor = REGISTRY.get(host)
    return bool(extractor and extractor.needs_js)


def is_known_domain(host: str) -> bool:
    return host in REGISTRY


@register_domain
class DemoShopExtractor(DomainExtractor):
    """Extractor for the bundled demo shop (radar-demo.internal)."""

    domains = ("radar-demo.internal", "demo.radar.local", "localhost")

    def extract(self, html: str, url: str) -> RawProduct:
        soup = BeautifulSoup(html, "lxml")
        product = RawProduct()

        from app.services.scraper.pricetext import parse_number

        name_el = soup.select_one("h1[data-radar='name']")
        if name_el:
            product.name = name_el.get_text(" ", strip=True)[:255]
        price_el = soup.select_one("[data-radar='price']")
        if price_el:
            product.price, product.currency = _price_value(price_el, "EUR")
            product.original_price = price_el.get("content") or price_el.get_text(" ", strip=True)
        prev_el = soup.select_one("[data-radar='old-price']")
        if prev_el:
            product.previous_price = parse_number(prev_el.get_text(" ", strip=True))
            product.original_previous_price = prev_el.get_text(" ", strip=True)
        promo_el = soup.select_one("[data-radar='promo']")
        if promo_el is not None:
            product.in_promotion = promo_el.get("value") != "false"
        avail_el = soup.select_one("[data-radar='availability']")
        if avail_el:
            product.availability = avail_el.get("data-state") or avail_el.get_text(" ", strip=True)
        stock_el = soup.select_one("[data-radar='stock']")
        if stock_el:
            product.stock_quantity = parse_number(stock_el.get("data-quantity") or stock_el.get_text(" ", strip=True))
        ean_el = soup.select_one("[data-radar='ean']")
        if ean_el:
            product.ean = ean_el.get_text(" ", strip=True)
        sku_el = soup.select_one("[data-radar='sku']")
        if sku_el:
            product.sku = sku_el.get_text(" ", strip=True)
        img_el = soup.select_one("[data-radar='image']")
        if img_el:
            product.image_url = img_el.get("src")
        ship_el = soup.select_one("[data-radar='shipping']")
        if ship_el:
            product.shipping_cost = parse_number(ship_el.get_text(" ", strip=True))
        return product


@register_domain
class JsDemoShopExtractor(DomainExtractor):
    """A demo store whose prices only exist after JS render."""

    domains = ("js-demo.radar.local",)
    needs_js = True

    def extract(self, html: str, url: str) -> RawProduct:
        soup = BeautifulSoup(html, "lxml")
        product = RawProduct()
        name_el = soup.select_one("[data-radar='name']")
        if name_el:
            product.name = name_el.get_text(" ", strip=True)[:255]
        price_el = soup.select_one("[data-radar='price']")
        if price_el:
            product.price, product.currency = _price_value(price_el, "EUR")
        avail_el = soup.select_one("[data-radar='availability']")
        if avail_el:
            product.availability = avail_el.get("data-state")
        return product


@register_domain
class JsonLdShopExtractor(DomainExtractor):
    """A store that publishes clean Product JSON-LD (schema.org)."""

    domains = ("jsonld-demo.radar.local",)

    def extract(self, html: str, url: str) -> RawProduct:
        soup = BeautifulSoup(html, "lxml")
        product = RawProduct()
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue
            offers = []
            if isinstance(data, dict) and data.get("@type") == "Product":
                product.name = data.get("name")
                product.sku = data.get("sku")
                offers = data.get("offers", [])
                if isinstance(offers, dict):
                    offers = [offers]
            for offer in offers:
                price, currency = normalize_price_local(offer.get("price"))
                if price is not None:
                    product.price = price
                    product.currency = offer.get("priceCurrency", "EUR")
                    product.original_price = str(offer.get("price"))
                    product.availability = offer.get("availability", "").split("/")[-1]
                    product.in_promotion = bool(offer.get("priceValidUntil")) or offer.get("availableAtOrFrom") is None
            return product
        return product


def normalize_price_local(v):
    from app.services.scraper.pricetext import normalize_price

    return normalize_price(str(v), "EUR")