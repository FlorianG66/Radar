"""Seed a rich demo environment (no external dependency).

Creates a demo user, its organization with a Pro trial and 6 monitored
products pointing at the bundled demo shop (localhost:8080), whose state
evolves so price drops, out-of-stock, back-in-stock and promotions appear
naturally over time.

Usage:
    python -m app.seed.demo         # seed data (requires migrated DB)
    python -m app.seed.demo --shop  # also start demo shop in a thread
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.models import Competitor, NotificationPreference, Organization, Plan, Product, Subscription, User
from app.services.subscription_service import ensure_all_plans

logger = logging.getLogger("radar.seed")

DEMO_PRODUCTS = [
    ("http://localhost:8080/p/rtx-5070", ""),
    ("http://localhost:8080/p/ssd-990-pro", ""),
    ("http://localhost:8080/p/monitor-27", ""),
    ("http://localhost:8080/p/keychron-k8", ""),
    ("http://localhost:8080/p/coffee-maker", ""),
    ("http://localhost:8080/p/js-product", ""),
]


def seed_demo() -> tuple[User, Organization]:
    from app.core import security

    db = SessionLocal()
    try:
        ensure_all_plans(db)
        existing = db.query(User).filter(User.email == "demo@radar.app").first()
        if existing:
            logger.info("demo user already present")
            return existing, db.get(Organization, existing.organization_id)

        org = Organization(name="Démo E-commerce", email="demo@radar.app")
        db.add(org)
        db.flush()

        user = User(
            email="demo@radar.app",
            first_name="Démo",
            last_name="Radar",
            hashed_password=security.hash_password("demo12345!"),
            organization_id=org.id,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.flush()

        plan = db.query(Plan).filter(Plan.slug == "pro").first()
        sub = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status="trialing",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
        db.add(sub)

        competitor_names = ["TechStore", "MegaEcho", "PixBox"]
        competitors: list[Competitor] = []
        for name in competitor_names:
            comp = Competitor(organization_id=org.id, name=name, domain="localhost")
            db.add(comp)
            competitors.append(comp)
        db.flush()

        for i, (url, name) in enumerate(DEMO_PRODUCTS):
            db.add(
                Product(
                    organization_id=org.id,
                    competitor_id=competitors[i % len(competitors)].id,
                    url=url,
                    name=name,
                    next_check_at=datetime.now(timezone.utc),
                )
            )

        pref = NotificationPreference(user_id=user.id, event_type="product_info", enabled=False)
        db.add(pref)

        db.commit()
        logger.info("demo seeded: user demo@radar.app / demo12345!")
        return user, org
    finally:
        db.close()


def main() -> None:
    from app.core.logging import setup_logging

    setup_logging()
    if "--shop" in sys.argv:
        from app.seed import demo_shop

        threading.Thread(target=demo_shop.run, daemon=True).start()
        time.sleep(0.5)
    seed_demo()
    print("Démo prête :")
    print("  email    : demo@radar.app")
    print("  password : demo12345!")
    print("  shop     : http://localhost:8080")


if __name__ == "__main__":
    main()