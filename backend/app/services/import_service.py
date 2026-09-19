"""CSV import/export of monitored products.

Minimal format:  url,nom,concurrent,categorie
Extra headers tolerated: name, competitor, category, sku.
"""
from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from app.models import Organization, Product
from app.schemas import ProductIn
from app.services import product_service
from app.services.subscription_service import LimitError

ALLOWED_SUFFIXES = (".csv", ".txt")

HEADER_ALIASES = {
    "url": "url",
    "nom": "name",
    "name": "name",
    "produit": "name",
    "concurrent": "competitor",
    "competitor": "competitor",
    "categorie": "category",
    "category": "category",
    "sku": "sku",
    "reference": "sku",
}


class CsvError(Exception):
    pass


def parse_rows(content: str) -> tuple[list[dict], list[dict], list[str]]:
    """Return (valid_rows, invalid_rows, errors)."""
    # strip BOM, normalize line breaks
    content = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    stream = io.StringIO(content)
    try:
        reader = csv.reader(stream)
        header = next(reader, None)
    except csv.Error as exc:
        raise CsvError(f"CSV illisible : {exc}") from exc
    if header is None:
        raise CsvError("fichier vide")

    fields = [HEADER_ALIASES.get(h.strip().lower(), "") for h in header]
    if "url" not in fields:
        raise CsvError("la colonne 'url' est obligatoire")

    valid: list[dict] = []
    invalid: list[dict] = []
    errors: list[str] = []
    for idx, row in enumerate(reader, start=2):
        if not row or all(not c.strip() for c in row):
            continue
        record = {name: (row[i].strip() if i < len(row) else "") for i, name in enumerate(fields)}
        url = record.get("url", "")
        try:
            url = product_service.validate_product_url(url)
        except product_service.ProductError as exc:
            errors.append(f"ligne {idx}: {exc}")
            invalid.append({"line": idx, "url": url, "error": str(exc)})
            continue
        valid.append({
            "url": url,
            "name": record.get("name") or "",
            "competitor": record.get("competitor") or "",
            "category": record.get("category") or "",
            "sku": record.get("sku") or "",
        })
    return valid, invalid, errors


def preview_import(content: str) -> dict:
    valid, invalid, errors = parse_rows(content)
    return {"valid_rows": valid, "invalid_rows": invalid, "errors": errors[:50]}


def run_import(db: Session, org: Organization, rows: list[dict], ignore_invalid: bool = True) -> dict:
    imported = 0
    skipped = 0
    errors: list[str] = []
    for row in rows:
        try:
            payload = ProductIn(
                url=row["url"],
                name=row.get("name") or "",
                competitor_name=row.get("competitor") or None,
                category=row.get("category") or None,
                sku=row.get("sku") or None,
            )
        except Exception as exc:
            skipped += 1
            errors.append(f"{row.get('url', '')}: {exc}")
            continue
        try:
            product_service.create_product(db, org, payload, check_limit=True)
            imported += 1
        except LimitError as exc:
            skipped += 1
            errors.append(str(exc))
            if not ignore_invalid:
                break
        except product_service.ProductError as exc:
            skipped += 1
            errors.append(str(exc))
    return {"imported": imported, "skipped": skipped, "errors": errors}


def export_csv(products: list[Product]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["nom", "url", "concurrent", "categorie", "sku", "dernier_prix", "devise", "disponibilite"])
    for p in products:
        writer.writerow([
            p.name,
            p.url,
            p.competitor.name if p.competitor else "",
            p.category or "",
            p.sku or "",
            p.last_price,
            p.currency or "",
            p.last_availability or "",
        ])
    return buf.getvalue()