"""Subscription & plan limit logic.

All plan limits are enforced here, server-side. The frontend may display
limits but the backend is the source of truth.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.plans import PLAN_CATALOG, TRIAL_PLAN_SLUG
from app.models import Organization, Plan, Subscription


class LimitError(Exception):
    pass


class PlanError(Exception):
    pass


def effective_plan_slug(db: Session, org: Organization) -> str:
    """Plan that applies to an organization. Canceled/incomplete falls back to Starter limits."""
    sub = current_subscription(db, org)
    if sub is None or sub.status in ("canceled", "incomplete", "incomplete_expired"):
        return "starter"
    return sub.plan.slug


def current_subscription(db: Session, org: Organization) -> Subscription | None:
    sub = (
        db.query(Subscription)
        .filter(Subscription.organization_id == org.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    return sub


def current_plan(db: Session, org: Organization) -> Plan:
    slug = effective_plan_slug(db, org)
    plan = db.query(Plan).filter(Plan.slug == slug).first()
    if plan is None:
        plan = _ensure_plan(db, slug)
    return plan


def _ensure_plan(db: Session, slug: str) -> Plan:
    p = PLAN_CATALOG[slug]
    plan = db.query(Plan).filter(Plan.slug == slug).first()
    if plan is None:
        plan = Plan(
            slug=p.slug,
            name=p.name,
            price_cents=p.price_cents,
            currency=p.currency,
            product_limit=p.product_limit,
            checks_per_day=p.checks_per_day,
            check_interval_hours=p.check_interval_hours,
            history_days=p.history_days,
            features=list(p.features),
        )
        db.add(plan)
        db.flush()
    return plan


def ensure_all_plans(db: Session) -> None:
    for slug in PLAN_CATALOG:
        _ensure_plan(db, slug)
    db.commit()


def product_limit(db: Session, org: Organization) -> int:
    return current_plan(db, org).product_limit


def history_retention_days(db: Session, org: Organization) -> int:
    return current_plan(db, org).history_days


def check_product_limit(db: Session, org: Organization, current_count: int) -> None:
    limit = product_limit(db, org)
    if current_count >= limit:
        raise LimitError(
            f"limite de {limit} produits atteinte pour votre plan. "
            "Passez à un plan supérieur pour surveiller plus de produits."
        )


def subscription_out(sub: Subscription | None, db: Session) -> dict | None:
    """Serialize a subscription with its plan, resistent to missing plan."""
    if sub is None:
        return None
    plan = db.get(Plan, sub.plan_id)
    return {
        "id": sub.id,
        "status": sub.status,
        "current_period_end": sub.current_period_end,
        "trial_ends_at": sub.trial_ends_at,
        "plan": {
            "slug": plan.slug if plan else None,
            "name": plan.name if plan else None,
            "price_cents": plan.price_cents if plan else 0,
            "currency": plan.currency if plan else "EUR",
            "product_limit": plan.product_limit if plan else 0,
            "checks_per_day": plan.checks_per_day if plan else 0,
            "history_days": plan.history_days if plan else 0,
            "features": plan.features if plan else [],
        },
    }