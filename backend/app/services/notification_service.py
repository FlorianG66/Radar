"""Notification preferences, anti-spam suppression and enqueueing."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.redis import redis_client
from app.models import ChangeEvent, Notification, NotificationPreference, Product, User

logger = logging.getLogger("radar.notifications")

DEFAULT_EVENT_PREFS = {
    "price_drop": True,
    "price_rise": True,
    "price_back": True,
    "out_of_stock": True,
    "in_stock": True,
    "promotion_start": True,
    "promotion_end": True,
    "promotion_change": False,
    "product_info": False,
    "scrape_failed": False,
}

# Do not re-alert for the same product+event type within this window.
SUPPRESSION_WINDOW_SECONDS = 12 * 3600


def get_prefs(db: Session, user: User, overrides: list[NotificationPreference] | None = None) -> dict[str, bool]:
    prefs = dict(DEFAULT_EVENT_PREFS)
    rows = overrides if overrides is not None else user.notification_preferences
    for row in rows:
        prefs[row.event_type] = row.enabled
    return prefs


def set_prefs(db: Session, user: User, prefs: dict[str, bool]) -> dict[str, bool]:
    for event_type, enabled in prefs.items():
        row = (
            db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user.id, NotificationPreference.event_type == event_type)
            .first()
        )
        if row:
            row.enabled = bool(enabled)
        else:
            db.add(NotificationPreference(user_id=user.id, event_type=event_type, enabled=bool(enabled)))
    db.commit()
    return get_prefs(db, user)


def should_suppress(product_id: int, event_type: str) -> bool:
    key = f"alert:{product_id}:{event_type}"
    if redis_client.set(key, "1", nx=True, ex=SUPPRESSION_WINDOW_SECONDS):
        return False
    return True


def alert_recipients(db: Session, org_id: int, event_type: str) -> list[User]:
    users = db.query(User).filter(User.organization_id == org_id, User.is_active.is_(True)).all()
    out = []
    for user in users:
        prefs = get_prefs(db, user)
        if prefs.get(event_type, False):
            out.append(user)
    return out


def create_notifications_for_event(db: Session, event: ChangeEvent) -> list[Notification]:
    """Create Notification rows for an event, respecting preferences and
    applying the anti-spam suppression window per product+event type."""
    recipients = alert_recipients(db, event.organization_id, event.event_type)
    created: list[Notification] = []
    product = db.get(Product, event.product_id)
    for user in recipients:
        if should_suppress(event.product_id, event.event_type):
            created.append(
                Notification(
                    organization_id=event.organization_id,
                    user_id=user.id,
                    event_id=event.id,
                    channel="email",
                    status="suppressed",
                    subject="(suppressed)",
                )
            )
        else:
            notif = Notification(
                organization_id=event.organization_id,
                user_id=user.id,
                event_id=event.id,
                channel="email",
                status="pending",
                subject=_build_subject(event, product),
            )
            db.add(notif)
            created.append(notif)
    if created:
        db.flush()
    return created


def _build_subject(event: ChangeEvent, product: Product | None) -> str:
    title = event.title
    product_name = product.name if product else ""
    state = event.new_state or {}
    if event.event_type.startswith("price") and "price" in state:
        title = f"{title} · {state['price']}"
    return f"[Radar] {product_name}: {title}"


def notification_history(db: Session, user: User, limit: int = 50) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )