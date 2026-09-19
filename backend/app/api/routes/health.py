"""Healthcheck and service status."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.redis import redis_client
from app.schemas import HealthOut

router = APIRouter(tags=["health"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/health", response_model=HealthOut)
def health(db: Db) -> HealthOut:
    db_ok = redis_ok = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = "error"
    try:
        redis_client.ping()
    except Exception:
        redis_ok = "error"
    return HealthOut(status="ok" if (db_ok == "ok" and redis_ok == "ok") else "degraded",
                     database=db_ok, redis=redis_ok)