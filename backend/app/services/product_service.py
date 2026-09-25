"""Product management, history, stats and limits enforcement."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from statistics import median
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import ChangeEvent, Competitor, Organization, Product, ProductSnapshot
from app.schemas import ProductIn, ProductUpdate

URL_RE = re.compile(r"^https?://(?:localhost(?::\d+)?|127\.0\.0\.1(?::\d+)?|[^\s/$.?#].[^\s]*)", re.IGNORECASE)


class ProductError(Exception):
    pass


class NotFoundError(Exception):
    pass


def validate_product_url(url: str) -> str:
    if not URL_RE.match(url):
        raise ProductError("URL invalide : elle doit être une URL http(s) complète")
    host = urlparse(url).netloc
    h = host.split(":")[0].lower()
    if not host or ("." not in h and h not in ("localhost", "127.0.0.1")):
        raise ProductError("URL invalide : domaine introuvable")
    return url


def _domain_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0]


def get_competitor_or_create(db: Session, org: Organization, name: str | None, url: str) -> Competitor | None:
    if not name:
        return None
    name = name.strip()
    if not name:
        return None
    existing = (
        db.query(Competitor)
        .filter(Competitor.organization_id == org.id, Competitor.name == name)
        .first()
    )
    if existing:
        return existing
    comp = Competitor(organization_id=org.id, name=name, domain=_domain_from_url(url))
    db.add(comp)
    db.flush()
    return comp


def create_competitor(db: Session, org: Organization, name: str) -> Competitor:
    existing = (
        db.query(Competitor)
        .filter(Competitor.organization_id == org.id, Competitor.name == name.strip())
        .first()
    )
    if existing:
        return existing
    comp = Competitor(organization_id=org.id, name=name.strip())
    db.add(comp)
    db.flush()
    return comp


def create_product(db: Session, org: Organization, payload: ProductIn, check_limit: bool = True) -> Product:
    from app.services.subscription_service import check_product_limit

    url = validate_product_url(str(payload.url))
    existing = db.query(Product).filter(Product.organization_id == org.id, Product.url == url).first()
    if existing:
        raise ProductError("cette URL est déjà surveillée")

    count = db.query(Product).filter(
        Product.organization_id == org.id, Product.is_active.is_(True)
    ).count()
    if check_limit:
        check_product_limit(db, org, count)

    competitor = None
    if payload.competitor_id:
        competitor = db.get(Competitor, payload.competitor_id)
        if not competitor or competitor.organization_id != org.id:
            raise ProductError("concurrent invalide")
    elif payload.competitor_name:
        competitor = get_competitor_or_create(db, org, payload.competitor_name, url)

    product = Product(
        organization_id=org.id,
        competitor_id=competitor.id if competitor else None,
        url=url,
        name=payload.name.strip() or _domain_from_url(url),
        category=payload.category,
        sku=payload.sku,
        check_interval_hours=payload.check_interval_hours,
        last_scrape_status="pending",
        next_check_at=datetime.now(timezone.utc),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def get_product(db: Session, org: Organization, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if not product or product.organization_id != org.id:
        raise NotFoundError("produit introuvable")
    return product


def update_product(db: Session, org: Organization, product_id: int, payload: ProductUpdate) -> Product:
    product = get_product(db, org, product_id)
    data = payload.model_dump(exclude_unset=True)
    if "competitor_id" in data and data["competitor_id"] is not None:
        comp = db.get(Competitor, data["competitor_id"])
        if not comp or comp.organization_id != org.id:
            raise ProductError("concurrent invalide")
    if "own_price" in data:
        product.own_price = data.pop("own_price")
        product.own_currency = data.pop("own_currency", product.own_currency)
        product.own_price_updated_at = datetime.now(timezone.utc)
    for field, value in data.items():
        if hasattr(product, field):
            setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, org: Organization, product_id: int) -> None:
    product = get_product(db, org, product_id)
    db.delete(product)
    db.commit()


def list_products(db: Session, org: Organization, search: str | None = None,
                  competitor_id: int | None = None, include_inactive: bool = False,
                  limit: int = 200, offset: int = 0) -> list[Product]:
    q = db.query(Product).filter(Product.organization_id == org.id)
    if not include_inactive:
        q = q.filter(Product.is_active.is_(True))
    if competitor_id:
        q = q.filter(Product.competitor_id == competitor_id)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    return q.order_by(Product.created_at.desc()).offset(offset).limit(limit).all()


def product_stats(db: Session, product: Product, history_days: int) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=history_days) if history_days else None
    q = db.query(ProductSnapshot).filter(ProductSnapshot.product_id == product.id)
    if cutoff:
        q = q.filter(ProductSnapshot.scraped_at >= cutoff)
    prices = [float(s.price) for s in q.all() if s.price is not None]
    if not prices:
        return {"count": 0, "min": None, "max": None, "median": None, "avg": None, "lowest_ever": None}
    return {
        "count": len(prices),
        "min": round(min(prices), 2),
        "max": round(max(prices), 2),
        "median": round(median(prices), 2),
        "avg": round(sum(prices) / len(prices), 2),
        "lowest_ever": round(min(prices), 2),
    }


def serialize_product(db: Session, product: Product, history_days: int) -> dict:
    competitor = product.competitor
    variation_abs = variation_pct = None
    if product.last_price is not None and product.previous_price is not None and product.previous_price:
        variation_abs = round(float(product.last_price) - float(product.previous_price), 2)
        variation_pct = round(variation_abs / float(product.previous_price) * 100, 2)
    return {
        "id": product.id,
        "url": product.url,
        "name": product.name,
        "category": product.category,
        "sku": product.sku,
        "check_interval_hours": float(product.check_interval_hours) if product.check_interval_hours else None,
        "is_active": product.is_active,
        "is_scraper_enabled": product.is_scraper_enabled,
        "last_price": float(product.last_price) if product.last_price is not None else None,
        "previous_price": float(product.previous_price) if product.previous_price is not None else None,
        "currency": product.currency,
        "last_availability": product.last_availability,
        "seen_promotion": product.seen_promotion,
        "last_scrape_status": product.last_scrape_status,
        "last_scrape_error": product.last_scrape_error,
        "last_checked_at": product.last_checked_at,
        "next_check_at": product.next_check_at,
        "created_at": product.created_at,
        "variation_abs": variation_abs,
        "variation_pct": variation_pct,
        "competitor_id": competitor.id if competitor else None,
        "competitor_name": competitor.name if competitor else None,
        "own_price": float(product.own_price) if product.own_price is not None else None,
        "own_currency": product.own_currency,
        "own_name": product.own_name,
        "stats": product_stats(db, product, history_days),
    }


def get_history(db: Session, org: Organization, product_id: int, days: int | None = None) -> tuple[Product, list[ProductSnapshot]]:
    product = get_product(db, org, product_id)
    q = db.query(ProductSnapshot).filter(ProductSnapshot.product_id == product.id)
    if days:
        q = q.filter(ProductSnapshot.scraped_at >= datetime.now(timezone.utc) - timedelta(days=days))
    snaps = q.order_by(ProductSnapshot.scraped_at.desc()).limit(1000).all()
    return product, snaps


def set_own_price(db: Session, org: Organization, product_id: int, price: float, currency: str, name: str = "") -> Product:
    product = get_product(db, org, product_id)
    product.own_price = price
    product.own_currency = currency
    if name:
        product.own_name = name
    product.own_price_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)
    return product


def recent_changes(db: Session, org: Organization, limit: int = 20) -> list[ChangeEvent]:
    return (
        db.query(ChangeEvent)
        .filter(ChangeEvent.organization_id == org.id)
        .order_by(ChangeEvent.created_at.desc())
        .limit(limit)
        .all()
    )