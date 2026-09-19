"""Password hashing, JWT creation/validation and token payload helpers."""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt as pyjwt

from app.core.config import get_settings

settings = get_settings()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _create_token(subject: str, token_type: str, lifetime: timedelta, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int, org_id: int | None) -> str:
    return _create_token(str(user_id), "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), {"org": org_id})


def create_refresh_token(user_id: int) -> str:
    return _create_token(str(user_id), "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def create_email_token(user_id: int) -> str:
    return _create_token(str(user_id), "email-verify", timedelta(days=1))


def create_password_reset_token(user_id: int) -> str:
    return _create_token(str(user_id), "password-reset", timedelta(hours=1))


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise ValueError("invalid token type")
    return payload