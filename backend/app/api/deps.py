"""Shared FastAPI dependencies: auth, org isolation, rate limiting."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import security
from app.core.db import get_db
from app.core.redis import redis_client
from app.models import Organization, User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentification requise")
    try:
        payload = security.decode_token(credentials.credentials, expected_type="access")
        user = db.get(User, int(payload["sub"]))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session invalide ou expirée")
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="compte désactivé")
    return user


def get_current_org(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Organization:
    if current_user.organization_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="aucune organisation")
    org = db.get(Organization, current_user.organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="organisation introuvable")
    return org


def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="accès administrateur requis")
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentOrg = Annotated[Organization, Depends(get_current_org)]
AdminUser = Annotated[User, Depends(require_admin)]


def rate_limit(max_requests: int, window_seconds: int):
    """Simple Redis fixed-window limiter. Distinct bucket per client+path.

    Rate limiting is skipped in the test environment so automated suites can
    exercise the endpoints without tripping on the shared "testclient" origin.
    """

    def dependency(request: Request) -> None:
        from app.core.config import get_settings

        if get_settings().ENVIRONMENT == "test":
            return
        if not redis_client:
            return
        key = f"rl:{request.client.host}:{request.url.path}"
        now = int(__import__("time").time())
        bucket = f"{key}:{now // window_seconds}"
        count = redis_client.incr(bucket)
        if count == 1:
            redis_client.expire(bucket, window_seconds + 10)
        if count > max_requests:
            raise HTTPException(status_code=429, detail="trop de requêtes, réessayez plus tard")

    return dependency