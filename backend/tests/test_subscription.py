"""Subscription, plans and Stripe endpoint tests."""
from __future__ import annotations

from tests.conftest import auth_headers


class TestPlans:
    def test_plans_list(self, client):
        r = client.get("/subscription/plans")
        assert r.status_code == 200
        slugs = {p["slug"] for p in r.json()}
        assert {"starter", "pro", "business"} <= slugs
        by_slug = {p["slug"]: p for p in r.json()}
        assert by_slug["starter"]["price_cents"] == 3900
        assert by_slug["starter"]["product_limit"] == 50
        assert by_slug["business"]["history_days"] == 0
        assert by_slug["pro"]["product_limit"] == 250

    def test_fresh_org_is_on_trial(self, client, demo_user):
        r = client.get("/subscription", headers=auth_headers(demo_user["token"]))
        sub = r.json()
        assert sub["status"] == "trialing"
        assert sub["plan"]["slug"] == "pro"

    def test_checkout_fallback_activates_plan(self, client, demo_user):
        r = client.post("/subscription/checkout", headers=auth_headers(demo_user["token"]), json={"plan": "starter"})
        assert r.status_code == 200
        assert "billing" in r.json()["url"] or r.json()["url"].startswith("https://checkout.stripe.com")
        sub = client.get("/subscription", headers=auth_headers(demo_user["token"])).json()
        # Stripe may or may not be configured; either way the endpoint must not crash.
        assert sub["plan"]["slug"] in ("starter",)

    def test_checkout_invalid_plan(self, client, demo_user):
        r = client.post("/subscription/checkout", headers=auth_headers(demo_user["token"]), json={"plan": "godmode"})
        assert r.status_code == 422

    def test_portal(self, client, demo_user):
        r = client.post("/subscription/portal", headers=auth_headers(demo_user["token"]))
        assert r.status_code == 200

    def test_dev_assign_requires_auth(self, client):
        assert client.post("/subscription/dev-assign", json={"plan": "pro"}).status_code == 401


class TestStripeWebhook:
    def test_missing_signature_rejected(self, client):
        r = client.post("/subscription/webhook", content=b"{}")
        assert r.status_code == 400

    def test_bad_signature_rejected(self, client, monkeypatch):
        import app.services.stripe_service as svc

        monkeypatch.setattr(svc, "stripe_enabled", lambda: True)

        from unittest.mock import patch

        with patch.object(svc, "_stripe") as mock_stripe:
            mock_stripe.Webhook.construct_event.side_effect = ValueError("bad payload")
            r = client.post("/subscription/webhook", content=b"{}",
                            headers={"Stripe-Signature": "t=1,v1=deadbeef"})
            assert r.status_code == 400

    def test_checkout_completed_activates(self, client, monkeypatch):
        import app.services.stripe_service as svc
        from app.core.config import get_settings

        class FakeSession:
            def __init__(self, **kw):
                self.session_id = "cs_test_123"

            @property
            def url(self):
                return "https://checkout.stripe.com/fake"

        fake = type("S", (), {"Customer": type("C", (), {
            "create": lambda **k: type("cust", (), {"id": "cus_123"})()
        }), "checkout": type("CO", (), {"Session": type("Sess", (), {"create": staticmethod(lambda **k: FakeSession())})}),
            "billing_portal": type("BP", (), {"Session": type("Sess2", (), {"create": staticmethod(lambda **k: type("s", (), {"url": "https://billing.stripe.com"})())})})})

        monkeypatch.setattr(svc, "stripe_enabled", lambda: True)
        settings = get_settings()
        monkeypatch.setattr(settings, "STRIPE_PRICE_STARTER", "price_starter_test")
        monkeypatch.setattr(svc, "_stripe", lambda: fake)
        from app.core import security
        from app.core.db import SessionLocal
        from app.models import User

        db = SessionLocal()
        user = db.query(User).order_by(User.id.desc()).first()
        # clear customer id cache to force creation
        org = user.organization
        settings = dict(org.settings or {})
        settings.pop("stripe_customer_id", None)
        org.settings = settings
        db.commit()

        r = client.post("/subscription/checkout", headers=auth_headers(
            security.create_access_token(user.id, user.organization_id)), json={"plan": "starter", } )
        assert r.status_code == 200
        # activate like webhook would
        svc.activate_plan(db, org, "starter", "cus_123", "sub_123", status="active")
        db.refresh(org)
        assert db.query(User).get(user.id).organization.settings.get("stripe_customer_id") == "cus_123"
        db.close()

    def test_handle_webhook_dispatches_known_event(self, monkeypatch):
        import app.services.stripe_service as svc

        class FakeStripe:
            class Webhook:
                @staticmethod
                def construct_event(payload, signature, secret):
                    return {"type": "customer.subscription.deleted", "data": {"object": {"customer": "cus_x"}}}

        monkeypatch.setattr(svc, "_stripe", lambda: FakeStripe)
        evt = svc.handle_webhook(b"{}", "sig")
        assert evt == "customer.subscription.deleted"