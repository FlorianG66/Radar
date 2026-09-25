"""Notifications: preferences and preference-based filtering."""
from __future__ import annotations

from tests.conftest import auth_headers

from app.models import ChangeEvent, Notification, Product
from app.services.notification_service import create_notifications_for_event, get_prefs


class TestPreferencesApi:
    def test_defaults_and_toggle(self, client, demo_user):
        r = client.get("/notifications/preferences/all", headers=auth_headers(demo_user["token"]))
        prefs = r.json()["prefs"]
        assert prefs["price_drop"] is True
        assert prefs["promotion_change"] is False

        client.put("/notifications/preferences", headers=auth_headers(demo_user["token"]),
                   json={"event_type": "price_drop", "enabled": False})
        r = client.get("/notifications/preferences/all", headers=auth_headers(demo_user["token"])).json()
        assert r["prefs"]["price_drop"] is False

    def test_history_endpoint(self, client, demo_user):
        r = client.get("/notifications", headers=auth_headers(demo_user["token"]))
        assert r.status_code == 200


class TestCreateNotifications:
    def _event(self, db, org, event_type):
        product = Product(organization_id=org.id, url=f"https://n.test/{event_type}", name=event_type)
        db.add(product)
        db.flush()
        event = ChangeEvent(organization_id=org.id, product_id=product.id,
                            event_type=event_type, importance="high",
                            old_state={}, new_state={})
        db.add(event)
        db.flush()
        return event

    def test_enabled_event_notifies_user(self, db, org_with_user):
        event = self._event(db, org_with_user, "price_drop")
        created = create_notifications_for_event(db, event)
        assert created
        assert created[0].status == "pending"
        db.commit()
        assert db.query(Notification).filter(Notification.event_id == event.id).count() == 1

    def test_disabled_event_does_not_notify(self, db, org_with_user):
        event = self._event(db, org_with_user, "promotion_change")
        created = create_notifications_for_event(db, event)
        assert created == []

    def test_unverified_user_not_notified(self, db):
        from datetime import timezone

        from app.core import security

        from app.models import Organization, Plan, Subscription, User

        org = Organization(name="Unverified", email="u@radartest.fr")
        db.add(org)
        db.flush()
        user = User(email="never-verified@radartest.fr", hashed_password=security.hash_password("x"),
                    organization_id=org.id, email_verified_at=None)
        db.add(user)
        plan = db.query(Plan).filter(Plan.slug == "pro").first()
        db.add(Subscription(organization_id=org.id, plan_id=plan.id, status="trialing"))
        event = self._event(db, org, "price_drop")
        assert create_notifications_for_event(db, event) == []

    def test_get_prefs_mask(self, db, org_with_user):
        from app.models import User

        user = db.query(User).filter(User.email.like("worker-user-%@radartest.fr")).first()
        prefs = get_prefs(db, user)
        assert prefs["price_drop"] is True
        assert set(prefs) == {
            "price_drop", "price_rise", "price_back", "out_of_stock", "in_stock",
            "promotion_start", "promotion_end", "promotion_change", "product_info", "scrape_failed",
        }