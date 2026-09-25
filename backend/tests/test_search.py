"""Product search by name (demo-shop + web)."""
from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from app.services.scraper.search import DemoShopSearchProvider, search_products

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load_html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestDemoShopProvider:
    def test_discovers_product_urls(self, monkeypatch):
        def fake(url, use_js=False):
            if url.startswith("http://localhost:8080/search"):
                return (
                    '<!doctype html><body>'
                    '<a data-radar="result" href="/p/rtx-5070">RTX 5070 12GB</a>'
                    '<a data-radar="result" href="/p/ssd-990-pro">Samsung 990 Pro 2TB</a>'
                    '</body>'
                )
            return "<html><body></body></html>"

        monkeypatch.setattr("app.services.scraper.search.fetch_html", fake)
        urls = DemoShopSearchProvider().discover("RTX", "localhost")
        assert "http://localhost:8080/p/rtx-5070" in urls

    def test_returns_empty_when_nothing_matches(self, monkeypatch):
        def fake(url, use_js=False):
            return '<!doctype html><body><p>aucun résultat</p></body>'

        monkeypatch.setattr("app.services.scraper.search.fetch_html", fake)
        urls = DemoShopSearchProvider().discover("xyz", "localhost")
        assert urls == []


class TestSearchOutcome:
    def test_finds_a_product_with_price(self, monkeypatch):
        def fake(url, use_js=False):
            if "/search" in url:
                return (
                    '<!doctype html><body>'
                    '<a data-radar="result" href="/p/rtx-5070">RTX 5070 12GB</a>'
                    '</body>'
                )
            if "/p/" in url:
                return load_html("js_page.html")
            return "<html><body></body></html>"

        monkeypatch.setattr("app.services.scraper.search.fetch_html", fake)
        monkeypatch.setattr("app.services.scraper.scraper_service.fetch_html", fake)

        outcome = search_products("RTX", [("DemoShop", "localhost")])
        assert outcome.results
        r = outcome.results[0]
        assert r.name == "Casque sans fil ANC"
        assert r.price == 179.0
        assert r.currency == "EUR"
        assert any(m.domain == "localhost" and m.ok for m in outcome.merchants)

    def test_merchant_reports_error_on_fetch_failure(self, monkeypatch):
        def fake(url, use_js=False):
            from app.services.scraper.fetcher import FetchError
            raise FetchError("timeout", retryable=True)

        monkeypatch.setattr("app.services.scraper.search.fetch_html", fake)
        outcome = search_products("RTX", [("DemoShop", "localhost")])
        assert not outcome.merchants[0].ok
        assert "timeout" in outcome.merchants[0].error
        assert outcome.results == []

    def test_empty_result_when_no_price(self, monkeypatch):
        def fake(url, use_js=False):
            if "/search" in url:
                return '<!doctype html><body><a data-radar="result" href="/p/ssd-990-pro">SSD</a></body>'
            return (
                "<!doctype html><body>"
                "<h1 data-radar='name'>SSD</h1>"
                "<p>pas de prix</p></body>"
            )

        monkeypatch.setattr("app.services.scraper.search.fetch_html", fake)
        monkeypatch.setattr("app.services.scraper.scraper_service.fetch_html", fake)

        outcome = search_products("SSD", [("DemoShop", "localhost")])
        assert outcome.results == []


class TestAPI:
    def _mock(self, monkeypatch):
        def search_html(url, use_js=False):
            if "duckduckgo" in url:
                return (
                    '<!doctype html><body>'
                    '<a class="result__a" href="https://fnac.com/p/rtx-5070">RTX 5070 12GB</a>'
                    '</body>'
                )
            return (
                '<!doctype html><body>'
                '<a data-radar="result" href="/p/rtx-5070">RTX 5070 12GB</a>'
                '</body>'
            )

        def product_html(url, use_js=False):
            if "fnac.com" in url:
                return load_html("plain_price.html")
            if "localhost" in url:
                return load_html("js_page.html")
            return "<html><body></body></html>"

        monkeypatch.setattr("app.services.scraper.search.fetch_html", search_html)
        monkeypatch.setattr("app.services.scraper.scraper_service.fetch_html", product_html)

    def test_search_returns_results(self, client, demo_user, monkeypatch):
        self._mock(monkeypatch)
        r = client.get(
            "/products/search?q=RTX",
            headers={"Authorization": f"Bearer {demo_user['token']}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["query"] == "RTX"
        assert len(data["results"]) > 0
        assert len(data["merchants"]) > 0
        assert data["results"][0]["price"] == 649.99
        assert data["results"][0]["domain"] == "fnac.com"

    def test_short_query_is_rejected(self, client, demo_user):
        r = client.get(
            "/products/search?q=ab",
            headers={"Authorization": f"Bearer {demo_user['token']}"},
        )
        assert r.status_code == 422

    def test_tracked_flag(self, client, demo_user, monkeypatch):
        self._mock(monkeypatch)
        product = client.post(
            "/products",
            headers={"Authorization": f"Bearer {demo_user['token']}"},
            json={
                "url": "https://fnac.com/p/rtx-5070",
                "name": "RTX 5070 12GB",
                "competitor_name": "Fnac",
            },
        )
        assert product.status_code == 201, product.text

        r = client.get(
            "/products/search?q=RTX",
            headers={"Authorization": f"Bearer {demo_user['token']}"},
        )
        assert r.status_code == 200
        tracked_results = [res for res in r.json()["results"] if res["url"] == "https://fnac.com/p/rtx-5070"]
        assert len(tracked_results) == 1
        assert tracked_results[0]["tracked"] is True
