"""CSV import/export endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentOrg, get_db
from app.models import Product
from app.schemas import CsvImportConfirm, CsvImportPreview, CsvImportResult, Message
from app.services import import_service
from app.services.subscription_service import LimitError

router = APIRouter(tags=["imports"])
Db = Annotated[Session, Depends(get_db)]


@router.post("/imports/csv/preview", response_model=CsvImportPreview)
async def preview_csv(file: UploadFile, _: CurrentOrg) -> dict:
    if not (file.filename or "").lower().endswith(import_service.ALLOWED_SUFFIXES):
        raise HTTPException(status_code=400, detail="fichier .csv attendu")
    content = (await file.read()).decode("utf-8", errors="replace")
    try:
        return import_service.preview_import(content)
    except import_service.CsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/imports/csv", response_model=CsvImportResult)
def confirm_import(payload: CsvImportConfirm, db: Db, org: CurrentOrg) -> CsvImportResult:
    rows = [r for r in payload.rows if r.get("url")]
    if not rows:
        raise HTTPException(status_code=400, detail="aucune ligne valide à importer")
    try:
        result = import_service.run_import(db, org, rows, ignore_invalid=payload.ignore_invalid)
    except LimitError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    return CsvImportResult(**result)


@router.get("/exports/products.csv", response_class=PlainTextResponse)
def export_products(db: Db, org: CurrentOrg) -> PlainTextResponse:
    products = (
        db.query(Product)
        .filter(Product.organization_id == org.id, Product.is_active.is_(True))
        .order_by(Product.name)
        .all()
    )
    csv_content = import_service.export_csv(products)
    return PlainTextResponse(csv_content, media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="radar-products.csv"'})