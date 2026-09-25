"""Scheduler loop: enqueues due product scrapes and performs maintenance.

API                 (never scrapes in request handlers)
  ↓
Scheduler  ──────►  Redis queue  ──────►  Workers  ──────►  DB / notifications
  │
  └─ maintenance: history pruning, stale job cleanup
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.jobs import enqueue_notification, enqueue_scrape
from app.core.redis import redis_client
from app.models import Product

logger = logging.getLogger("radar.scheduler")

STALE_JOB_AGE_HOURS = 2
KEEP_JOB_DAYS = 30


def _enqueue_scrape(product_id: int) -> bool:
    guard = f"queued:{product_id}"
    if redis_client.get(guard):
        return False
    redis_client.set(guard, "1", ex=3600)
    try:
        return enqueue_scrape(product_id)
    except Exception:
        redis_client.delete(guard)
        raise


def enqueue_due_scrapes() -> int:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due = (
            db.query(Product)
            .filter(
                Product.is_active.is_(True),
                Product.is_scraper_enabled.is_(True),
                (Product.next_check_at.is_(None)) | (Product.next_check_at <= now),
            )
            .limit(2000)
            .all()
        )
        count = 0
        for product in due:
            try:
                if _enqueue_scrape(product.id):
                    count += 1
            except Exception:
                logger.exception("failed to enqueue product %s", product.id)
        return count
    finally:
        db.close()


def requeue_pending_notifications() -> int:
    """Re-enqueue notification processing for pending notifications that were not picked yet."""
    db = SessionLocal()
    try:
        pending = (
            db.query(Notification)
            .filter(Notification.status == "pending")
            .order_by(Notification.created_at.asc())
            .limit(200)
            .all()
        )
        count = 0
        for notif in pending:
            if not notif.event_id:
                notif.status = "suppressed"
                db.add(notif)
                continue
            if not redis_client.get(f"notif:queued:{notif.id}"):
                redis_client.set(f"notif:queued:{notif.id}", "1", ex=3600)
                if enqueue_notification(notif.event_id):
                    count += 1
        db.commit()
        return count
    finally:
        db.close()


def prune_snapshots() -> int:
    """Delete snapshots older than the organization's plan retention window."""
    db = SessionLocal()
    try:
        from app.models import Organization, Plan, Product, ProductSnapshot, Subscription

        deleted = 0
        orgs = db.query(Organization).all()
        for org in orgs:
            retention = 30
            sub = (
                db.query(Subscription)
                .filter(Subscription.organization_id == org.id)
                .order_by(Subscription.created_at.desc())
                .first()
            )
            if sub and sub.plan_id:
                plan = db.get(Plan, sub.plan_id)
                if plan:
                    retention = plan.history_days
            if not retention:
                continue  # unlimited
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
            product_ids = [p.id for p in db.query(Product).filter(Product.organization_id == org.id).all()]
            if not product_ids:
                continue
            keep_latest = (
                db.query(ProductSnapshot)
                .filter(ProductSnapshot.product_id.in_(product_ids), ProductSnapshot.scraped_at < cutoff)
            )
            deleted += keep_latest.count()
            keep_latest.delete(synchronize_session=False)
        db.commit()
        return deleted
    finally:
        db.close()


def cleanup_stale_jobs() -> int:
    db = SessionLocal()
    try:
        from app.models import ScrapeJob

        stale = (
            db.query(ScrapeJob)
            .filter(ScrapeJob.status.in_(["queued", "running"]), ScrapeJob.scheduled_at < datetime.now(timezone.utc) - timedelta(hours=STALE_JOB_AGE_HOURS))
            .all()
        )
        for job in stale:
            job.status = "failed"
            job.error = "job laissé en attente, considéré comme échoué"
            db.add(job)
        old_cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_JOB_DAYS)
        db.query(ScrapeJob).filter(ScrapeJob.scheduled_at < old_cutoff).delete(synchronize_session=False)
        db.commit()
        return len(stale)
    finally:
        db.close()


def run_forever(poll_seconds: int | None = None) -> None:
    settings = get_settings()
    poll = poll_seconds or settings.SCHEDULER_POLL_SECONDS
    logger.info("scheduler started poll=%s", poll)
    last_prune = 0.0
    while True:
        started = time.monotonic()
        try:
            enqueued = enqueue_due_scrapes()
            if enqueued:
                logger.info("enqueued %s scrapes", enqueued)
            requeue_pending_notifications()
        except Exception:
            logger.exception("scheduler cycle error")
        now_ts = time.monotonic()
        if now_ts - last_prune > 3600:
            try:
                pruned = prune_snapshots()
                stale = cleanup_stale_jobs()
                if pruned or stale:
                    logger.info("maintenance pruned_snapshots=%s stale_jobs=%s", pruned, stale)
            except Exception:
                logger.exception("maintenance error")
            last_prune = now_ts
        elapsed = time.monotonic() - started
        time.sleep(max(0, poll - elapsed))


if __name__ == "__main__":
    from app.core.logging import setup_logging

    setup_logging()
    run_forever()