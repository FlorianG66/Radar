"""Dashboard, changes feed and notifications endpoints."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentOrg, CurrentUser, get_db
from app.models import ChangeEvent, Notification, Organization, Product, ScrapeJob
from app.schemas import (
    ChangeEventOut,
    DashboardOut,
    Message,
    NotificationOut,
    NotificationPrefItem,
    NotificationPreferences,
    ProductOut,
)
from app.services import notification_service, product_service
from app.services.subscription_service import current_subscription, history_retention_days, subscription_out

router = APIRouter(tags=["dashboard"])
Db = Annotated[Session, Depends(get_db)]


def _event_out(db: Session, event: ChangeEvent) -> ChangeEventOut:
    product = db.get(Product, event.product_id)
    return ChangeEventOut(
        id=event.id,
        event_type=event.event_type,
        importance=event.importance,
        title=event.title,
        old_state=event.old_state,
        new_state=event.new_state,
        created_at=event.created_at,
        product_id=event.product_id,
        product_name=product.name if product else None,
        product_url=product.url if product else None,
        competitor_name=product.competitor.name if product and product.competitor else None,
    )


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Db, org: CurrentOrg, days: int = Query(1, ge=1, le=30)) -> DashboardOut:
    now = datetime.now(timezone.utc)
    start = datetime.combine(now, time.min)
    retention = history_retention_days(db, org)

    products = db.query(Product).filter(Product.organization_id == org.id).all()
    products_count = len(products)
    active = [p for p in products if p.is_active]

    events_q = db.query(ChangeEvent).filter(
        ChangeEvent.organization_id == org.id,
        ChangeEvent.created_at >= start - timedelta(days=days),
    )
    today_events = events_q.all()

    drops = sum(1 for e in today_events if e.event_type == "price_drop")
    rises = sum(1 for e in today_events if e.event_type == "price_rise")
    outages = sum(1 for e in today_events if e.event_type == "out_of_stock")
    errors = sum(1 for p in products if p.last_scrape_status == "error")
    checks_today = (
        db.query(ScrapeJob)
        .filter(ScrapeJob.scheduled_at >= start - timedelta(days=days))
    ).count()

    recent = product_service.recent_changes(db, org, limit=15)
    preview = [_to_product(db, org, p) for p in active[:20]]

    sub = current_subscription(db, org)
    return DashboardOut(
        products_count=products_count,
        active_products=len(active),
        changes_today=len(today_events),
        price_drops_today=drops,
        price_rises_today=rises,
        out_of_stock_today=outages,
        scrape_errors=errors,
        checks_today=checks_today,
        plan=subscription_out(sub, db),
        recent_changes=[_event_out(db, e) for e in recent],
        product_preview=preview,
    )


def _to_product(db: Session, org: Organization, p: Product) -> ProductOut:
    return ProductOut.model_validate(product_service.serialize_product(db, p, history_retention_days(db, org)))


@router.get("/changes", response_model=list[ChangeEventOut])
def list_changes(
    db: Db,
    org: CurrentOrg,
    limit: int = Query(50, le=200),
    event_type: str | None = None,
    product_id: int | None = None,
) -> list[ChangeEventOut]:
    q = db.query(ChangeEvent).filter(ChangeEvent.organization_id == org.id)
    if event_type:
        q = q.filter(ChangeEvent.event_type == event_type)
    if product_id:
        q = q.filter(ChangeEvent.product_id == product_id)
    events = q.order_by(ChangeEvent.created_at.desc()).limit(limit).all()
    return [_event_out(db, e) for e in events]


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(db: Db, user: CurrentUser, limit: int = Query(50, le=200)) -> list[NotificationOut]:
    rows = notification_service.notification_history(db, user, limit=limit)
    out = []
    for n in rows:
        event_type = None
        product_name = None
        if n.event_id:
            event = db.get(ChangeEvent, n.event_id)
            if event:
                event_type = event.event_type
                product = db.get(Product, event.product_id)
                product_name = product.name if product else None
        out.append(NotificationOut(
            id=n.id, channel=n.channel, status=n.status, subject=n.subject,
            created_at=n.created_at, event_type=event_type, product_name=product_name,
        ))
    return out


@router.get("/notifications/preferences", response_model=NotificationPreferences)
def get_prefs(user: CurrentUser) -> NotificationPreferences:
    return NotificationPreferences(prefs=notification_service.get_prefs(None, user, list(user.notification_preferences)))


@router.put("/notifications/preferences", response_model=NotificationPreferences)
def put_prefs(payload: NotificationPrefItem, user: CurrentUser, db: Db) -> NotificationPreferences:
    prefs = notification_service.set_prefs(db, user, {payload.event_type: payload.enabled})
    return NotificationPreferences(prefs=prefs)


@router.get("/notifications/preferences/all", response_model=NotificationPreferences)
def get_all_prefs(user: CurrentUser, db: Db) -> NotificationPreferences:
    return NotificationPreferences(prefs=notification_service.get_prefs(db, user))