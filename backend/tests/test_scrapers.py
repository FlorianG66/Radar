"""Scraper extractors tested with HTML fixtures."""
from __future__ import annotations

import pathlib

from app.services.scraper.domains import DemoShopExtractor, JsonLdShopExtractor
from app.services.scraper.extractor import GenericExtractor
from app.services.scraper.fetcher import FetchError
from app.services.scraper.scraper_service import scrape_url

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load_html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestGenericExtractor:
    def test_european_plain_price(self):
        p = GenericExtractor().extract(load_html("plain_price.html"), "http://mystore.test/p/1")
        assert p.price == 649.99
        assert p.currency == "EUR"
        assert p.name in ("Exemple européen", None) or p.name

    def test_jsonld(self):
        p = GenericExtractor().extract(load_html("jsonld_product.html"), "http://shop.test/p/1")
        assert p.price == 129.00
        assert p.name == "Mechanical Keyboard Pro"
        assert p.sku == "MK-PRO-1"
        assert p.ean == "3986400100327"
        assert p.availability == "in_stock"
        assert p.in_promotion is False

    def test_microdata(self):
        p = GenericExtractor().extract(load_html("microdata.html"), "http://shop.test/p/2")
        assert p.price == 39.9
        assert p.currency == "EUR"
        assert p.name == "USB-C Hub 7en1"
        assert p.sku == "HUB-7"
        assert p.availability == "in_stock"

    def test_open_graph(self):
        p = GenericExtractor().extract(load_html("og.html"), "http://techshop.example/casque")
        assert p.price == 89.99
        assert p.name == "Casque Bluetooth ANC"
        assert p.image_url.startswith("https://img.techshop/")

    def test_out_of_stock(self):
        p = GenericExtractor().extract(load_html("out_of_stock.html"), "http://shop.test/p/4")
        assert p.price == 59.0
        assert p.availability == "out_of_stock"

    def test_promo_with_old_price(self):
        p = GenericExtractor().extract(load_html("promo.html"), "http://shop.test/p/5")
        assert p.price == 499.0
        assert p.previous_price == 649.0
        assert p.in_promotion is True

    def test_broken_page_no_price(self):
        p = GenericExtractor().extract(load_html("broken.html"), "http://shop.test/p/6")
        assert p.price is None


class TestDomainExtractors:
    def test_demo_shop(self):
        p = DemoShopExtractor().extract(load_html("js_page.html"), "http://demo.radar.local/p/1")
        assert p.price == 179.0
        assert p.name == "Casque sans fil ANC"
        assert p.availability == "in_stock"

    def test_jsonld_shop(self):
        p = JsonLdShopExtractor().extract(load_html("jsonld_product.html"), "http://jsonld-demo.radar.local/p/1")
        assert p.price == 129.0
        assert p.name == "Mechanical Keyboard Pro"


class TestScrapeUrl:
    def _monkeypatch_fetch(self, monkeypatch, html: str | Exception):
        def fake(url, use_js=False):
            if isinstance(html, Exception):
                raise html
            if isinstance(html, dict):
                for prefix, content in html.items():
                    if url.startswith(prefix):
                        return content
                return html.get("__default__", "")
            return html
        monkeypatch.setattr("app.services.scraper.scraper_service.fetch_html", fake)

    def test_success_generic(self, monkeypatch):
        self._monkeypatch_fetch(monkeypatch, load_html("plain_price.html"))
        out = scrape_url("http://mystore.test/p/1")
        assert out.success
        assert out.raw.price == 649.99

    def test_success_demo_shop(self, monkeypatch):
        self._monkeypatch_fetch(monkeypatch, load_html("js_page.html"))
        out = scrape_url("http://demo.radar.local/p/1")
        assert out.success
        assert out.raw.price == 179.0
        assert out.raw.name == "Casque sans fil ANC"

    def test_no_price_is_not_success(self, monkeypatch):
        self._monkeypatch_fetch(monkeypatch, load_html("broken.html"))
        out = scrape_url("http://mystore.test/p/6")
        assert not out.success
        assert out.raw is None or out.raw.price is None

    def test_http_error(self, monkeypatch):
        self._monkeypatch_fetch(monkeypatch, FetchError("HTTP 500", status=500, retryable=True))
        out = scrape_url("http://mystore.test/p/7")
        assert not out.success
        assert out.http_status == 500
        assert out.error == "HTTP 500"

    def test_timeout(self, monkeypatch):
        self._monkeypatch_fetch(monkeypatch, FetchError("timeout", retryable=True))
        out = scrape_url("http://mystore.test/p/8")
        assert not out.success
        assert "timeout" in (out.error or "")

    def test_disabled_domain(self, monkeypatch, db):
        from app.models import DomainState

        db.add(DomainState(domain="mystore.test", disabled=True))
        db.commit()
        self._monkeypatch_fetch(monkeypatch, load_html("plain_price.html"))
        out = scrape_url("http://mystore.test/p/1", db)
        assert not out.success
        assert out.domain_disabled

    def test_changed_structure(self, monkeypatch):
        # structure changed: generic selectors still hopefully find a price
        html = '<html><body><h1>Carte graphique</h1><div class="product-price-block">2 149,00 €</div></body></html>'
        self._monkeypatch_fetch(monkeypatch, html)
        out = scrape_url("http://mystore.test/p/9")
        assert out.success
        assert out.raw.price == 2149.0