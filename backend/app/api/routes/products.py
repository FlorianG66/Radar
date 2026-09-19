"""Products, competitors, history & own-price endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentOrg, CurrentUser, get_db
from app.core.redis import scrape_queue
from app.models import Competitor, Product, ProductSnapshot
from app.schemas import (
    CompetitorIn,
    CompetitorOut,
    ProductIn,
    ProductOut,
    ProductUpdate,
    ProductWithOwnPriceIn,
    SnapshotOut,
    Message,
)
from app.services import product_service
from app.services.subscription_service import history_retention_days
from app.workers.tasks import process_scrape

router = APIRouter(tags=["products"])
Db = Annotated[Session, Depends(get_db)]


def _to_out(db: Session, product: Product, retention: int) -> ProductOut:
    return ProductOut.model_validate(product_service.serialize_product(db, product, retention))


@router.get("/competitors", response_model=list[CompetitorOut])
def list_competitors(db: Db, org: CurrentOrg) -> list[dict]:
    comps = db.query(Competitor).filter(Competitor.organization_id == org.id).order_by(Competitor.name).all()
    out = []
    for c in comps:
        count = db.query(Product).filter(Product.organization_id == org.id, Product.competitor_id == c.id).count()
        out.append({"id": c.id, "name": c.name, "domain": c.domain, "products_count": count})
    return out


@router.post("/competitors", response_model=CompetitorOut, status_code=status.HTTP_201_CREATED)
def create_competitor(payload: CompetitorIn, db: Db, org: CurrentOrg) -> Competitor:
    return product_service.create_competitor(db, org, payload.name)


@router.get("/products", response_model=list[ProductOut])
def list_products(
    db: Db,
    org: CurrentOrg,
    search: str | None = None,
    competitor_id: int | None = None,
    limit: int = Query(200, le=500),
    offset: int = 0,
) -> list[ProductOut]:
    retention = history_retention_days(db, org)
    products = product_service.list_products(db, org, search=search, competitor_id=competitor_id, limit=limit, offset=offset)
    return [_to_out(db, p, retention) for p in products]


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductIn, db: Db, org: CurrentOrg) -> ProductOut:
    from app.services.subscription_service import LimitError

    try:
        product = product_service.create_product(db, org, payload)
    except LimitError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc
    except product_service.ProductError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_out(db, product, history_retention_days(db, org))


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Db, org: CurrentOrg) -> ProductOut:
    try:
        product = product_service.get_product(db, org, product_id)
    except product_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_out(db, product, history_retention_days(db, org))


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductUpdate, db: Db, org: CurrentOrg) -> ProductOut:
    try:
        product = product_service.update_product(db, org, product_id, payload)
    except product_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except product_service.ProductError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_out(db, product, history_retention_days(db, org))


@router.delete("/products/{product_id}", response_model=Message)
def delete_product(product_id: int, db: Db, org: CurrentOrg) -> Message:
    try:
        product_service.delete_product(db, org, product_id)
    except product_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Message(message="produit supprimé")


@router.post("/products/{product_id}/scrape", response_model=Message)
def trigger_scrape(product_id: int, db: Db, org: CurrentOrg) -> Message:
    try:
        product = product_service.get_product(db, org, product_id)
    except product_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    scrape_queue.enqueue(process_scrape, product.id, job_timeout=180, result_ttl=86400)
    return Message(message="vérification planifiée")


@router.get("/products/{product_id}/history")
def get_history(product_id: int, db: Db, org: CurrentOrg, days: int | None = Query(None, ge=1, le=366)) -> dict:
    try:
        product, snaps = product_service.get_history(db, org, product_id, days=days)
    except product_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    own = []
    if product.own_price is not None:
        own = [{"price": float(product.own_price), "currency": product.own_currency, "at": product.own_price_updated_at}]
    retention = history_retention_days(db, org)
    return {
        "product": _to_out(db, product, retention), 
        "snapshots": [SnapshotOut.model_validate(s) for s in snaps],
        "own_prices": own,
    }


@router.post("/products/{product_id}/own-price", response_model=ProductOut)
def set_own_price(product_id: int, payload: ProductWithOwnPriceIn, db: Db, org: CurrentOrg) -> ProductOut:
    try:
        product = product_service.set_own_price(db, org, product_id, payload.own_price, payload.own_currency, payload.own_name)
    except product_service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_out(db, product, history_retention_days(db, org))