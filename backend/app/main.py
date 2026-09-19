"""API entrypoint and router mounting."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, dashboard, health, imports, products, subscription
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.services.subscription_service import ensure_all_plans

settings = get_settings()
setup_logging()
logger = logging.getLogger("radar.app")

app = FastAPI(
    title="Radar API",
    description=(
        "Voici le changement chez vos concurrents. Radar surveille les prix, "
        "la disponibilité et les promotions des produits de vos concurrents "
        "et vous alerte automatiquement."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "Radar", "url": settings.FRONTEND_URL},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (health.router, auth.router, products.router, dashboard.router,
               imports.router, subscription.router, admin.router):
    app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    try:
        from app.core.db import SessionLocal

        db = SessionLocal()
        try:
            ensure_all_plans(db)
        finally:
            db.close()
        logger.info("plans ensured")
    except Exception:
        logger.exception("startup check failed (db unavailable?)")


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": "Radar API", "docs": "/docs", "version": "0.1.0"}