"""Admin stats + scheduler maintenance tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.conftest import auth_headers

from app.models import Product, ProductSnapshot


def _make_admin(db, email=None):
    import uuid

    from app.core import security

    from app.models import User

    if email is None:
        email = f"admin-{uuid.uuid4().hex[:8]}@radartest.fr"
    user = User(email=email, hashed_password=security.hash_password("x"), is_admin=True)
    db.add(user)
    db.commit()
    from app.core.security import create_access_token

    return create_access_token(user.id, None)


class TestAdmin:
    def test_admin_stats(self, client, db, org_with_user):
        token = _make_admin(db)
        r = client.get("/admin/stats", headers=auth_headers(token))
        assert r.status_code == 200
        body = r.json()
        assert body["organizations"] >= 1
        assert isinstance(body["domains"], list)

    def test_admin_list_organizations(self, client, db, org_with_user):
        token = _make_admin(db)
        r = client.get("/admin/organizations", headers=auth_headers(token))
        assert r.status_code == 200
        names = [o["name"] for o in r.json()]
        assert any(n.startswith("WorkerOrg") for n in names)

    def test_disable_enable_domain(self, client, db):
        token = _make_admin(db, "admin2@radartest.fr")
        r = client.post("/admin/domains/demo.radar.local/disable", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["disabled"] is True
        lst = client.get("/admin/domains", headers=auth_headers(token)).json()
        entry = next(d for d in lst if d["name"] == "demo.radar.local")
        assert entry["disabled"] is True
        r = client.post("/admin/domains/demo.radar.local/enable", headers=auth_headers(token))
        assert r.json()["disabled"] is False

    def test_unknown_domain(self, client, db):
        token = _make_admin(db, "admin3@radartest.fr")
        assert client.post("/admin/domains/zzz.test/disable", headers=auth_headers(token)).status_code == 404

    def test_pause_org_scrapers(self, client, db, org_with_user):
        token = _make_admin(db, "admin4@radartest.fr")
        product = Product(organization_id=org_with_user.id, url="https://x.test/p/1", name="X")
        db.add(product)
        db.commit()
        r = client.delete(f"/admin/organizations/{org_with_user.id}/scrapers", headers=auth_headers(token))
        assert r.status_code == 200
        assert db.get(Product, product.id).is_scraper_enabled is False


class TestScheduler:
    def test_enqueue_due_scrapes(self, db, org_with_user):
        from app.workers.scheduler import enqueue_due_scrapes

        product = Product(organization_id=org_with_user.id, url="https://due.test/p/1", name="Due",
                          next_check_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        db.add(product)
        db.commit()
        assert enqueue_due_scrapes() >= 1

    def test_prune_snapshots_respects_retention(self, db, org_with_user):
        from app.workers.scheduler import prune_snapshots

        keeper = Product(organization_id=org_with_user.id, url="https://prune.test/p/keep", name="Keep")
        dropper = Product(organization_id=org_with_user.id, url="https://prune.test/p/drop", name="Drop")
        db.add_all([keeper, dropper])
        db.flush()
        old = datetime.now(timezone.utc) - timedelta(days=400)  # beyond Pro(365)
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        db.add_all([
            ProductSnapshot(product_id=keeper.id, scraped_at=recent, price=10),
            ProductSnapshot(product_id=dropper.id, scraped_at=old, price=10),
        ])
        db.commit()
        deleted = prune_snapshots()
        assert deleted >= 1
        assert db.query(ProductSnapshot).filter(ProductSnapshot.product_id == keeper.id).count() == 1
        assert db.query(ProductSnapshot).filter(ProductSnapshot.product_id == dropper.id).count() == 0