"""Subscription & Stripe endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentOrg, CurrentUser, get_db
from app.core.config import get_settings
from app.schemas import CheckoutRequest, CheckoutResponse, Message, PortalResponse, SubscriptionOut
from app.services import stripe_service
from app.services.subscription_service import (
    current_subscription,
    ensure_all_plans,
    subscription_out,
)
from app.schemas import PlanOut

router = APIRouter(prefix="/subscription", tags=["subscription"])
Db = Annotated[Session, Depends(get_db)]


@router.get("", response_model=SubscriptionOut)
def get_subscription(db: Db, org: CurrentOrg) -> dict | None:
    return subscription_out(current_subscription(db, org), db)


@router.get("/plans", response_model=list[PlanOut])
def list_plans(db: Db) -> list[PlanOut]:
    ensure_all_plans(db)
    from app.models import Plan

    plans = db.query(Plan).order_by(Plan.price_cents).all()
    out = []
    for p in plans:
        out.append(PlanOut(
            slug=p.slug, name=p.name, price_cents=p.price_cents, currency=p.currency,
            product_limit=p.product_limit, checks_per_day=p.checks_per_day,
            history_days=p.history_days,
            features=[f for f in (p.features or [])],
        ))
    return out


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutRequest, db: Db, org: CurrentOrg) -> CheckoutResponse:
    try:
        url = stripe_service.create_checkout(db, org, payload.plan, payload.success_url, payload.cancel_url)
    except stripe_service.StripeServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CheckoutResponse(url=url)


@router.post("/portal", response_model=PortalResponse)
def portal(db: Db, org: CurrentOrg) -> PortalResponse:
    return PortalResponse(url=stripe_service.create_portal(db, org))


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, signature: Annotated[str | None, Header()] = None) -> dict:
    payload = await request.body()
    try:
        etype = stripe_service.handle_webhook(payload, signature)
    except stripe_service.StripeServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"received": True, "type": etype}


@router.post("/dev-assign", response_model=SubscriptionOut, include_in_schema=False)
def dev_assign(payload: CheckoutRequest, db: Db, org: CurrentOrg) -> dict | None:
    """Development helper: assign a plan directly without Stripe."""
    if stripe_service.stripe_enabled() and get_settings().ENVIRONMENT != "development":
        raise HTTPException(status_code=403, detail="interdit hors développement")
    stripe_service.activate_plan(db, org, payload.plan, None, None, status="active")
    return subscription_out(current_subscription(db, org), db)