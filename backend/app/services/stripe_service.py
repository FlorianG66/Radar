"""Stripe integration: customers, checkout, portal, webhooks.

When STRIPE_SECRET_KEY is not configured (pure local development) the service
falls back to an instant "fake checkout" so the whole product remains
exerciseable without third-party credentials.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.plans import PLAN_CATALOG
from app.models import Organization, Plan, Subscription, User

logger = logging.getLogger("radar.stripe")


class StripeServiceError(Exception):
    pass


def stripe_enabled() -> bool:
    return get_settings().stripe_enabled


def _stripe():
    import stripe

    settings = get_settings()
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _price_id_for(plan_slug: str) -> str:
    env_name = PLAN_CATALOG[plan_slug].stripe_price_id_env
    return getattr(get_settings(), env_name, "")


def plan_slug_for_price(price_id: str) -> str | None:
    settings = get_settings()
    mapping = {
        settings.STRIPE_PRICE_STARTER: "starter",
        settings.STRIPE_PRICE_PRO: "pro",
        settings.STRIPE_PRICE_BUSINESS: "business",
    }
    return mapping.get(price_id)


def _ensure_customer(db: Session, org: Organization) -> str:
    if org.settings.get("stripe_customer_id"):
        return org.settings["stripe_customer_id"]
    stripe = _stripe()
    cust = stripe.Customer.create(
        email=org.email,
        name=org.name,
        metadata={"radar_org_id": str(org.id)},
    )
    settings = org.settings or {}
    settings["stripe_customer_id"] = cust.id
    org.settings = settings
    db.commit()
    return cust.id


def create_checkout(db: Session, org: Organization, plan_slug: str,
                    success_url: str | None = None, cancel_url: str | None = None) -> str:
    settings = get_settings()
    if not stripe_enabled():
        # Local/dev fallback: activate immediately, no external dependency.
        return _fake_checkout(db, org, plan_slug)

    price_id = _price_id_for(plan_slug)
    if not price_id:
        raise StripeServiceError("le prix Stripe n'est pas configuré pour ce plan")

    customer_id = _ensure_customer(db, org)
    stripe = _stripe()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url or f"{settings.FRONTEND_URL}/billing?status=success",
        cancel_url=cancel_url or f"{settings.FRONTEND_URL}/billing?status=canceled",
        subscription_data={
            "trial_period_days": settings.STRIPE_TRIAL_DAYS,
            "metadata": {"radar_org_id": str(org.id)},
        },
        metadata={"radar_org_id": str(org.id), "radar_plan": plan_slug},
        allow_promotion_codes=True,
    )
    return session.url


def create_portal(db: Session, org: Organization) -> str:
    settings = get_settings()
    customer_id = org.settings.get("stripe_customer_id")
    if not stripe_enabled() or not customer_id:
        return f"{settings.FRONTEND_URL}/billing"
    stripe = _stripe()
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=f"{settings.FRONTEND_URL}/billing")
    return session.url


def _fake_checkout(db: Session, org: Organization, plan_slug: str) -> str:
    activate_plan(db, org, plan_slug, stripe_customer_id=None, stripe_subscription_id=None, status="active")
    settings = get_settings()
    return f"{settings.FRONTEND_URL}/billing?status=success&fake=1"


def activate_plan(db: Session, org: Organization, plan_slug: str, stripe_customer_id: str | None,
                  stripe_subscription_id: str | None, status: str = "active") -> Subscription:
    from datetime import datetime, timedelta, timezone

    plan = db.query(Plan).filter(Plan.slug == plan_slug).first()
    if plan is None:
        raise StripeServiceError(f"plan {plan_slug} inconnu en base")

    now = datetime.now(timezone.utc)
    existing = (
        db.query(Subscription)
        .filter(Subscription.organization_id == org.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if existing:
        existing.plan_id = plan.id
        existing.status = status
        existing.stripe_customer_id = stripe_customer_id or existing.stripe_customer_id
        existing.stripe_subscription_id = stripe_subscription_id or existing.stripe_subscription_id
        existing.current_period_end = now + timedelta(days=30)
        existing.trial_ends_at = None
        sub = existing
    else:
        sub = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            status=status,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            current_period_end=now + timedelta(days=30),
        )
        db.add(sub)
    if stripe_customer_id:
        settings = org.settings or {}
        settings["stripe_customer_id"] = stripe_customer_id
        org.settings = settings
    db.commit()
    db.refresh(sub)
    return sub


def cancel_subscription(db: Session, org: Organization) -> Subscription | None:
    sub = (
        db.query(Subscription)
        .filter(Subscription.organization_id == org.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if sub is None:
        return None
    sub.status = "canceled"
    db.commit()
    db.refresh(sub)
    return sub


def handle_webhook(payload: bytes, signature: str | None) -> str:
    settings = get_settings()
    if not settings.STRIPE_WEBHOOK_SECRET or not signature:
        raise StripeServiceError("webhook signature manquante")
    import stripe

    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError as exc:
        raise StripeServiceError("payload invalide") from exc
    except stripe.SignatureVerificationError as exc:
        raise StripeServiceError("signature invalide") from exc
    return _route_event(event)


def _route_event(event) -> str:
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        etype = event["type"]
        data = event["data"]["object"]
        if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            _on_checkout_completed(db, data)
        elif etype == "customer.subscription.updated":
            _on_subscription_updated(db, data)
        elif etype == "customer.subscription.deleted":
            _on_subscription_deleted(db, data)
        elif etype == "invoice.payment_failed":
            _on_payment_failed(db, data)
        return etype
    finally:
        db.close()


def _org_by_stripe_id(db: Session, customer_id: str) -> Organization | None:
    return (
        db.query(Organization)
        .filter(Organization.settings["stripe_customer_id"].astext == customer_id)
        .first()
    )


def _org_by_metadata(db: Session, meta: dict) -> Organization | None:
    org_id = meta.get("radar_org_id")
    if org_id:
        return db.get(Organization, int(org_id))
    return None


def _on_checkout_completed(db: Session, obj: dict) -> None:
    meta = obj.get("metadata") or {}
    customer = obj.get("customer")
    sub_id = obj.get("subscription")
    plan_slug = meta.get("radar_plan") or plan_slug_for_price(_price_from_subscription(db, sub_id))
    org = _org_by_metadata(db, meta) or _org_by_stripe_id(db, customer)
    if org is None or not plan_slug:
        logger.warning("checkout completed: org or plan not resolved (%s)", obj.get("id"))
        return
    activate_plan(db, org, plan_slug, stripe_customer_id=customer, stripe_subscription_id=sub_id, status="active")


def _price_from_subscription(db: Session, sub_id: str | None) -> str | None:
    if not sub_id or not stripe_enabled():
        return None
    stripe = _stripe()
    try:
        sub = stripe.Subscription.retrieve(sub_id)
    except Exception:
        return None
    items = sub.get("items", {}).get("data", [])
    if items:
        return items[0].get("price", {}).get("id")
    return None


def _on_subscription_updated(db: Session, obj: dict) -> None:
    customer = obj.get("customer")
    status = obj.get("status")
    org = _org_by_stripe_id(db, customer)
    if org is None:
        return
    sub = (
        db.query(Subscription)
        .filter(Subscription.organization_id == org.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if sub is None:
        return
    sub.status = status if status in ("active", "trialing", "past_due", "incomplete", "canceled") else "incomplete"
    sub.stripe_subscription_id = obj.get("id") or sub.stripe_subscription_id
    period_end = obj.get("current_period_end")
    if period_end:
        from datetime import datetime
        sub.current_period_end = datetime.fromtimestamp(period_end)
    plan_slug = plan_slug_for_price(_price_from_subscription(db, obj.get("id")))
    if plan_slug:
        plan = db.query(Plan).filter(Plan.slug == plan_slug).first()
        if plan:
            sub.plan_id = plan.id
    db.commit()


def _on_subscription_deleted(db: Session, obj: dict) -> None:
    org = _org_by_stripe_id(db, obj.get("customer"))
    if org is None:
        return
    cancel_subscription(db, org)


def _on_payment_failed(db: Session, obj: dict) -> None:
    customer = obj.get("customer")
    org = _org_by_stripe_id(db, customer)
    if org is None:
        return
    sub = (
        db.query(Subscription)
        .filter(Subscription.organization_id == org.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if sub:
        sub.status = "past_due"
        db.commit()