"""Shared pytest fixtures.

A dedicated SQLite database is used for the whole test session so that the
API, the services and the worker tasks all share the same data without
touching a real Postgres/Redis infrastructure.
"""
from __future__ import annotations

import os
import pathlib
import tempfile

# Must be set before importing any app module.
_env_dir = pathlib.Path(tempfile.mkdtemp(prefix="radar-test-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{( _env_dir / 'test.db').as_posix()}")
os.environ["SECRET_KEY"] = "test-secret-key-not-for-prod"
os.environ["SMTP_BACKEND"] = "console"
os.environ["ENVIRONMENT"] = "test"
os.environ["FRONTEND_URL"] = "http://test.local"
os.environ["API_BASE_URL"] = "http://test.local"
os.environ["STRIPE_SECRET_KEY"] = ""
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    from app.core.db import Base, SessionLocal, engine
    from app.services.subscription_service import ensure_all_plans

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_all_plans(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    from app.core.db import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def demo_user(client):
    """Register a fresh user and return (user, org, token)."""
    import uuid

    email = f"demo-{uuid.uuid4().hex[:8]}@radartest.fr"
    resp = client.post("/auth/register", json={
        "email": email,
        "password": "Str0ngPassword!",
        "first_name": "Test",
        "last_name": "User",
        "organization_name": "ACME",
    })
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    org = client.get("/auth/me/org", headers={"Authorization": f"Bearer {token}"}).json()
    return {"email": email, "token": token, "user": me, "org": org}


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def demo_product(client, demo_user):
    resp = client.post(
        "/products",
        headers=auth_headers(demo_user["token"]),
        json={"url": "http://mystore.test/p/123", "name": "Produit test", "competitor_name": "ConcurrentX",
              "category": "GPU"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def org_with_user(db):
    """Organization with a verified user + pro subscription, ready for worker tests."""
    import uuid
    from datetime import datetime, timezone

    from app.core import security

    from app.models import Organization, Plan, Subscription, User

    org = Organization(name=f"WorkerOrg-{uuid.uuid4().hex[:8]}", email="worker@radartest.fr")
    db.add(org)
    db.flush()
    user = User(
        email=f"worker-user-{uuid.uuid4().hex[:8]}@radartest.fr",
        hashed_password=security.hash_password("unused"),
        organization_id=org.id,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    plan = db.query(Plan).filter(Plan.slug == "pro").first()
    db.add(Subscription(organization_id=org.id, plan_id=plan.id, status="trialing"))
    db.commit()
    return org