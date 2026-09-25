"""End-to-end worker tests: scrape → snapshot → detection → notifications,
with HTTP fetch stubbed via HTML fixtures."""
from __future__ import annotations

import pathlib

from app.models import ChangeEvent, Notification, Product, ProductSnapshot, ScrapeJob
from app.workers.tasks import process_scrape

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


PLAIN = None
CHANGED = None


def _stub_fetch(monkeypatch, html: str | Exception):
    def fake(url, use_js=False):
        if isinstance(html, Exception):
            raise html
        return html
    monkeypatch.setattr("app.services.scraper.scraper_service.fetch_html", fake)


def _new_product(db, org, url: str, name: str = "") -> Product:
    product = Product(organization_id=org.id, url=url, name=name, last_scrape_status="pending")
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _fresh(db):
    """Drop cached identity-map state so reads reflect worker sessions."""
    db.expire_all()


class TestWorkerLoop:
    def test_first_scrape_stores_snapshot_no_event(self, db, org_with_user, monkeypatch):
        _stub_fetch(monkeypatch, load("plain_price.html"))
        product = _new_product(db, org_with_user, "https://worker.test/p/1", "Test")
        res = process_scrape(product.id)
        _fresh(db)
        assert res.startswith("ok:")
        assert db.query(ProductSnapshot).filter(ProductSnapshot.product_id == product.id).count() == 1
        assert db.query(ChangeEvent).filter(ChangeEvent.product_id == product.id).count() == 0
        p = db.get(Product, product.id)
        assert float(p.last_price) == 649.99
        assert p.last_scrape_status == "ok"

    def test_price_change_generates_event_and_notification(self, db, org_with_user, monkeypatch):
        _stub_fetch(monkeypatch, load("plain_price.html"))
        product = _new_product(db, org_with_user, "https://worker.test/p/2", "Test2")
        process_scrape(product.id)
        _stub_fetch(monkeypatch, '<html><body><span class="price">599,99 €</span></body></html>')
        process_scrape(product.id)
        _fresh(db)
        events = db.query(ChangeEvent).filter(ChangeEvent.product_id == product.id).all()
        assert [e.event_type for e in events] == ["price_drop"]
        assert events[0].importance == "high"
        notifs = db.query(Notification).filter(Notification.event_id == events[0].id).all()
        assert notifs and notifs[0].status == "pending"

    def test_out_of_stock_detected(self, db, org_with_user, monkeypatch):
        _stub_fetch(monkeypatch, load("plain_price.html"))
        product = _new_product(db, org_with_user, "https://worker.test/p/3")
        process_scrape(product.id)
        _stub_fetch(monkeypatch, load("out_of_stock.html"))
        process_scrape(product.id)
        _fresh(db)
        events = db.query(ChangeEvent).filter(ChangeEvent.product_id == product.id).all()
        assert "out_of_stock" in [e.event_type for e in events]

    def test_failure_never_writes_snapshot_nor_event(self, db, org_with_user, monkeypatch):
        from app.services.scraper.fetcher import FetchError

        _stub_fetch(monkeypatch, FetchError("HTTP 500", status=500))
        product = _new_product(db, org_with_user, "https://worker.test/p/4")
        res = process_scrape(product.id)
        _fresh(db)
        assert res.startswith("failed:")
        assert db.query(ProductSnapshot).filter(ProductSnapshot.product_id == product.id).count() == 0
        assert db.query(ChangeEvent).filter(ChangeEvent.product_id == product.id).count() == 0
        p = db.get(Product, product.id)
        assert p.last_scrape_status == "error"
        assert p.last_scrape_error == "HTTP 500"
        job = db.query(ScrapeJob).filter(ScrapeJob.product_id == product.id).order_by(ScrapeJob.id.desc()).first()
        assert job.status == "failed"
        assert job.http_status == 500

    def test_broken_page_is_failure_not_change(self, db, org_with_user, monkeypatch):
        _stub_fetch(monkeypatch, load("plain_price.html"))
        product = _new_product(db, org_with_user, "https://worker.test/p/5")
        process_scrape(product.id)
        _stub_fetch(monkeypatch, load("broken.html"))
        process_scrape(product.id)
        _fresh(db)
        assert db.query(ChangeEvent).filter(ChangeEvent.product_id == product.id).count() == 0
        assert db.query(ProductSnapshot).filter(ProductSnapshot.product_id == product.id).count() == 1
        assert db.get(Product, product.id).last_scrape_status == "error"

    def test_inactive_product_skipped(self, db, org_with_user, monkeypatch):
        _stub_fetch(monkeypatch, load("plain_price.html"))
        product = _new_product(db, org_with_user, "https://worker.test/p/6")
        product.is_active = False
        db.commit()
        assert process_scrape(product.id) == "skipped"

    def test_lock_prevents_concurrent_duplicates(self, db, monkeypatch):
        from app.core.redis import redis_client

        redis_client.set("scrape:lock:999999", "1", ex=600)
        assert process_scrape(999999) == "already_running"
        redis_client.delete("scrape:lock:999999")