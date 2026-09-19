"""Admin endpoints (admins only)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import AdminUser, CurrentOrg, get_db
from app.core.redis import redis_client
from app.models import (
    ChangeEvent,
    DomainState,
    Organization,
    Product,
    ScrapeJob,
    Subscription,
    User,
)
from app.schemas import AdminStats, DomainKeyOut, Message, OrgAdminOut
from app.services.scraper.domains import REGISTRY

router = APIRouter(prefix="/admin", tags=["admin"])
Db = Annotated[Session, Depends(get_db)]


def _plan_slug(db: Session, org_id: int) -> str | None:
    sub = (
        db.query(Subscription)
        .filter(Subscription.organization_id == org_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if sub and sub.plan_id:
        plan = sub.plan
        if plan:
            return plan.slug
    return None


@router.get("/stats", response_model=AdminStats)
def stats(db: Db, _: AdminUser) -> AdminStats:
    now = datetime.now(timezone.utc)
    per_domain = (
        db.query(Product.url, Product.last_scrape_status)
        .all()
    )
    domain_count: dict[str, dict] = {}
    for url, status in per_domain:
        if not url:
            continue
        domain = url.split("/")[2].lower().removeprefix("www.")
        entry = domain_count.setdefault(domain, {"scrapes": 0, "errors": 0})
        entry["scrapes"] += 1
        if status == "error":
            entry["errors"] += 1
    domains = [{"domain": k, **v} for k, v in sorted(domain_count.items(), key=lambda x: -x[1]["scrapes"])]

    failures = (
        db.query(ScrapeJob, Product)
        .join(Product, ScrapeJob.product_id == Product.id)
        .filter(ScrapeJob.status == "failed", ScrapeJob.finished_at >= now - timedelta(days=7))
        .order_by(ScrapeJob.finished_at.desc())
        .limit(20)
        .all()
    )
    recent_failures = [
        {
            "id": job.id,
            "product_id": product.id,
            "url": product.url,
            "error": job.error,
            "finished_at": job.finished_at,
            "http_status": job.http_status,
        }
        for job, product in failures
    ]

    queued_jobs = len(redis_client.keys("rq:queue:*")) if redis_client else 0
    failed_jobs_count = db.query(ScrapeJob).filter(ScrapeJob.status == "failed").count()

    subscriptions: dict[str, int] = {}
    for sub in db.query(Subscription).all():
        slug = sub.plan.slug if sub.plan else "?"
        subscriptions[f"{slug}:{sub.status}"] = subscriptions.get(f"{slug}:{sub.status}", 0) + 1

    return AdminStats(
        users=db.query(User).count(),
        organizations=db.query(Organization).count(),
        products=db.query(Product).count(),
        snapshots=0,
        change_events=db.query(ChangeEvent).count(),
        scrape_errors=db.query(Product).filter(Product.last_scrape_status == "error").count(),
        failed_jobs=failed_jobs_count,
        queued_jobs=queued_jobs,
        subscriptions=subscriptions,
        domains=domains,
        recent_failures=recent_failures,
    )


@router.get("/organizations", response_model=list[OrgAdminOut])
def list_organizations(db: Db, _: AdminUser) -> list[dict]:
    orgs = db.query(Organization).order_by(Organization.created_at.desc()).limit(200).all()
    out = []
    for o in orgs:
        out.append({
            "id": o.id,
            "name": o.name,
            "email": o.email,
            "created_at": o.created_at,
            "products_count": db.query(Product).filter(Product.organization_id == o.id).count(),
            "users_count": db.query(User).filter(User.organization_id == o.id).count(),
            "plan_slug": _plan_slug(db, o.id),
        })
    return out


@router.get("/domains", response_model=list[DomainKeyOut])
def list_domains(db: Db, _: AdminUser) -> list[DomainKeyOut]:
    states = {s.domain: s for s in db.query(DomainState).all()}
    out = []
    for host in sorted(REGISTRY.keys()):
        state = states.get(host)
        out.append(DomainKeyOut(
            id=state.id if state else 0,
            name=host,
            disabled=bool(state and state.disabled),
            disabled_reason=state.disabled_reason if state else None,
        ))
    return out


@router.post("/domains/{domain}/disable", response_model=DomainKeyOut)
def disable_domain(domain: str, db: Db, _: AdminUser) -> DomainKeyOut:
    if domain not in REGISTRY:
        raise HTTPException(status_code=404, detail="domaine inconnu")
    state = db.query(DomainState).filter(DomainState.domain == domain).first()
    if state is None:
        state = DomainState(domain=domain)
        db.add(state)
    state.disabled = True
    db.commit()
    return DomainKeyOut(id=state.id, name=domain, disabled=True)


@router.post("/domains/{domain}/enable", response_model=DomainKeyOut)
def enable_domain(domain: str, db: Db, _: AdminUser) -> DomainKeyOut:
    state = db.query(DomainState).filter(DomainState.domain == domain).first()
    if state is None:
        raise HTTPException(status_code=404, detail="état du domaine inconnu")
    state.disabled = False
    state.disabled_reason = None
    db.commit()
    return DomainKeyOut(id=state.id, name=domain, disabled=False)


@router.delete("/organizations/{org_id}/scrapers", response_model=Message)
def pause_org_scrapers(org_id: int, db: Db, _: AdminUser) -> Message:
    db.query(Product).filter(Product.organization_id == org_id, Product.is_scraper_enabled.is_(True)).update(
        {"is_scraper_enabled": False, "last_scrape_status": "disabled"}
    )
    db.commit()
    return Message(message="scraping désactivé pour l'organisation")