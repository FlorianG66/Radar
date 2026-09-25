"""RQ task functions executed by the workers.

process_scrape  — runs the scraping pipeline for one product,
                   stores the snapshot, detects changes,
                   persists events and schedules notifications.
process_event_notifications — sends the queued emails for an event.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.plans import PLAN_CATALOG
from app.core.redis import redis_client
from app.mail import html_password_reset, html_verify_email, send_email
from app.mail.sender import _shell, template_button
from app.models import (
    ChangeEvent,
    Notification,
    Organization,
    Plan,
    Product,
    ProductSnapshot,
    ScrapeJob,
    Subscription,
    User,
)
from app.services.detection import SnapshotView, detect
from app.services.notification_service import create_notifications_for_event
from app.services.scraper import scrape_url

logger = logging.getLogger("radar.worker")

RETRY_DELAY_ON_FAILURE_MINUTES = 30


def _retention_days(db: Session, org_id: int) -> int:
    sub = (
        db.query(Subscription)
        .filter(Subscription.organization_id == org_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if sub and sub.status not in ("canceled", "incomplete", "incomplete_expired") and sub.plan_id:
        plan = db.get(Plan, sub.plan_id)
        if plan:
            return plan.history_days
    return PLAN_CATALOG["starter"].history_days


def process_scrape(product_id: int) -> str:
    """Scrape one product. Never raises for content/network issues."""
    lock = redis_client.set(f"scrape:lock:{product_id}", "1", nx=True, ex=600)
    if not lock:
        return "already_running"

    db = SessionLocal()
    try:
        product = db.get(Product, product_id)
        if product is None or not product.is_active or not product.is_scraper_enabled:
            return "skipped"

        job = ScrapeJob(product_id=product_id, status="running", started_at=datetime.now(timezone.utc))
        db.add(job)
        db.commit()

        outcome = scrape_url(product.url, db=db)

        if outcome.success and outcome.raw.price is not None:
            return _handle_success(db, product, job, outcome)
        else:
            return _handle_failure(db, product, job, outcome.error, outcome.http_status, outcome.domain_disabled)
    finally:
        redis_client.delete(f"scrape:lock:{product_id}")
        db.close()


def _handle_success(db: Session, product: Product, job: ScrapeJob, outcome) -> str:
    raw = outcome.raw
    now = datetime.now(timezone.utc)

    snap = ProductSnapshot(
        product_id=product.id,
        scraped_at=now,
        price=raw.price,
        original_price=(raw.original_price or "")[:64],
        currency=raw.currency or product.currency or "EUR",
        previous_price=raw.previous_price,
        original_previous_price=(raw.original_previous_price or "")[:64] or None,
        availability=raw.availability,
        stock_quantity=raw.stock_quantity,
        in_promotion=raw.in_promotion,
        shipping_cost=raw.shipping_cost,
        shipping_currency=raw.currency,
        product_name=(raw.name or "")[:255] or None,
        product_sku=raw.sku,
        ean=raw.ean,
        image_url=raw.image_url,
        raw_data=raw.extras or None,
    )
    db.add(snap)
    db.flush()

    # previous = latest snapshot before this one
    prev_snap = (
        db.query(ProductSnapshot)
        .filter(ProductSnapshot.product_id == product.id, ProductSnapshot.id != snap.id)
        .order_by(ProductSnapshot.scraped_at.desc())
        .first()
    )
    older = (
        db.query(ProductSnapshot)
        .filter(ProductSnapshot.product_id == product.id, ProductSnapshot.id != snap.id)
        .order_by(ProductSnapshot.scraped_at.desc())
        .offset(1)
        .limit(10)
        .all()
    )
    prev_view = SnapshotView.from_orm(prev_snap) if prev_snap else None
    older_views = [SnapshotView.from_orm(s) for s in older]

    events = detect(prev_view, SnapshotView.from_orm(snap), older_views)
    changed = len(events) > 0

    # denormalize product state
    product.last_price = snap.price
    product.previous_price = snap.previous_price
    product.currency = snap.currency
    product.last_availability = snap.availability
    product.seen_promotion = snap.in_promotion or product.seen_promotion
    product.last_scrape_status = "ok"
    product.last_scrape_error = None
    product.last_checked_at = now
    product.next_check_at = now + _interval(product)
    if raw.name and len(raw.name) >= 3 and (not product.name or product.name == _fallback_name(product)):
        product.name = raw.name[:255]

    job.status = "success"
    job.finished_at = now
    job.duration_ms = outcome.duration_ms
    job.http_status = outcome.http_status
    db.commit()

    _persist_events(db, product, events, snap)
    return f"ok:snapshot={snap.id}:events={len(events)}"


def _fallback_name(product: Product) -> str:
    from urllib.parse import urlparse

    host = urlparse(product.url).netloc.lower()
    return host.removeprefix("www.")


def _interval(product: Product) -> timedelta:
    hours = float(product.check_interval_hours) if product.check_interval_hours else 24.0
    return timedelta(hours=hours)


def _persist_events(db: Session, product: Product, events, snap: ProductSnapshot) -> None:
    for evt in events:
        event = ChangeEvent(
            organization_id=product.organization_id,
            product_id=product.id,
            event_type=evt.event_type,
            importance=evt.importance,
            old_state=evt.old_state,
            new_state=evt.new_state,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()
        create_notifications_for_event(db, event)
    if events:
        db.commit()


def _handle_failure(db: Session, product: Product, job: ScrapeJob, error: str | None,
                    http_status: int | None, domain_disabled: bool) -> str:
    now = datetime.now(timezone.utc)
    if domain_disabled:
        product.is_scraper_enabled = False
        product.last_scrape_status = "disabled"
    else:
        product.last_scrape_status = "error"
    product.last_scrape_error = (error or "erreur inconnue")[:255]
    product.last_checked_at = now
    # Retry sooner on transient failures, but always gracefully.
    retry = timedelta(minutes=RETRY_DELAY_ON_FAILURE_MINUTES if not domain_disabled else 60 * 24)
    product.next_check_at = now + retry

    job.status = "failed"
    job.finished_at = now
    job.error = (error or "")[:255]
    job.http_status = http_status
    db.commit()
    logger.warning("scrape failed product=%s url=%s error=%s", product.id, product.url, error)
    return f"failed:{error}"


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
def _event_email(event: ChangeEvent, product: Product, user: User) -> str:
    competitor = product.competitor.name if product.competitor else "concurrent"
    icon = {"price_drop": "🔴", "price_rise": "🟠", "out_of_stock": "🟠",
            "in_stock": "🟢", "promotion_start": "🔴"}.get(event.event_type, "🟡")
    old = event.old_state or {}
    new = event.new_state or {}
    lines = []
    if "price" in old and "price" in new:
        lines.append(f"Prix : {old['price']} → <strong>{new['price']}</strong> {new.get('currency', '')}")
    if "availability" in old and "availability" in new:
        lines.append(f"Disponibilité : {old['availability']} → <strong>{new['availability']}</strong>")
    detail = "<br>".join(lines) or "Détail : voir le produit."
    settings = get_settings()
    return _shell(
        f'<p style="font-size:18px;font-weight:700;">{icon} {event.title}</p>'
        f'<p style="color:#64748b;">{product.name}</p>'
        f'<p style="color:#64748b;">Concurrent : {competitor}</p>'
        f'<p style="margin:16px 0;padding:12px;background:#f8fafc;border-radius:8px;">{detail}</p>'
        + template_button("Voir le produit", f"{settings.FRONTEND_URL}/products/{product.id}")
    )


def process_event_notifications(event_id: int) -> str:
    db = SessionLocal()
    try:
        event = db.get(ChangeEvent, event_id)
        if event is None:
            return "event_not_found"
        product = db.get(Product, event.product_id)
        notifs = db.query(Notification).filter(Notification.event_id == event.id, Notification.status == "pending").all()
        for notif in notifs:
            user = db.get(User, notif.user_id)
            if user is None or not user.email_verified_at:
                notif.status = "suppressed"
                db.add(notif)
                continue
            try:
                send_email(user.email, notif.subject or "Alerte Radar", _event_email(event, product, user))
                notif.status = "sent"
                notif.sent_at = datetime.now(timezone.utc)
            except Exception as exc:
                notif.status = "failed"
                notif.error = str(exc)[:255]
                logger.warning("email send failed notif=%s: %s", notif.id, exc)
            db.add(notif)
        db.commit()
        return f"sent:{len(notifs)}"
    finally:
        db.close()