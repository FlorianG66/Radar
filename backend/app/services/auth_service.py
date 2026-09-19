"""Authentication flows: register, login, refresh, verify, reset."""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.mail import html_password_reset, html_verify_email, send_email
from app.models import Organization, Plan, Subscription, User
from app.schemas import LoginRequest, RegisterRequest


class AuthError(Exception):
    pass


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def register(db: Session, payload: RegisterRequest) -> tuple[User, Organization]:
    email = _normalize_email(payload.email)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise AuthError("un compte avec cet email existe déjà")

    org = Organization(name=payload.organization_name or "Mon entreprise", email=email)
    db.add(org)
    db.flush()

    user = User(
        email=email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        hashed_password=security.hash_password(payload.password),
        organization_id=org.id,
    )
    db.add(user)
    db.flush()

    _default_trial_subscription(db, org)
    db.commit()

    token = security.create_email_token(user.id)
    url = f"{get_settings().FRONTEND_URL}/verify-email?token={token}"
    send_email(email, "Confirmez votre adresse email", html_verify_email(url))
    return user, org


def _default_trial_subscription(db: Session, org: Organization) -> None:
    from app.core.plans import TRIAL_PLAN_SLUG, PLAN_CATALOG
    from datetime import datetime, timedelta, timezone

    plan = db.query(Plan).filter(Plan.slug == TRIAL_PLAN_SLUG).first()
    if plan is None:
        plan_slug = TRIAL_PLAN_SLUG
        p = PLAN_CATALOG[plan_slug]
        plan = Plan(
            slug=p.slug, name=p.name, price_cents=p.price_cents, currency=p.currency,
            product_limit=p.product_limit, checks_per_day=p.checks_per_day,
            check_interval_hours=p.check_interval_hours, history_days=p.history_days,
            features=list(p.features),
        )
        db.add(plan)
        db.flush()
    now = datetime.now(timezone.utc)
    sub = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status="trialing",
        trial_ends_at=now + timedelta(days=get_settings().STRIPE_TRIAL_DAYS),
    )
    db.add(sub)
    return None


def login(db: Session, payload: LoginRequest) -> tuple[User, str, str]:
    email = _normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not security.verify_password(payload.password, user.hashed_password):
        raise AuthError("email ou mot de passe incorrect")
    if not user.is_active:
        raise AuthError("ce compte est désactivé")
    access = security.create_access_token(user.id, user.organization_id)
    refresh = security.create_refresh_token(user.id)
    return user, access, refresh


def refresh_tokens(db: Session, refresh_token: str) -> tuple[str, str]:
    try:
        payload = security.decode_token(refresh_token, expected_type="refresh")
    except Exception as exc:
        raise AuthError("session expirée, reconnectez-vous") from exc
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise AuthError("utilisateur invalide")
    access = security.create_access_token(user.id, user.organization_id)
    new_refresh = security.create_refresh_token(user.id)
    return access, new_refresh


def verify_email(db: Session, token: str) -> User:
    try:
        payload = security.decode_token(token, expected_type="email-verify")
    except Exception as exc:
        raise AuthError("lien de vérification invalide ou expiré") from exc
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise AuthError("utilisateur introuvable")
    from datetime import datetime, timezone

    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def forgot_password(db: Session, email: str) -> None:
    user = db.query(User).filter(User.email == _normalize_email(email)).first()
    if not user:
        # Do not leak which emails exist.
        return
    token = security.create_password_reset_token(user.id)
    url = f"{get_settings().FRONTEND_URL}/reset-password?token={token}"
    send_email(user.email, "Réinitialisation de votre mot de passe", html_password_reset(url))


def reset_password(db: Session, token: str, new_password: str) -> None:
    try:
        payload = security.decode_token(token, expected_type="password-reset")
    except Exception as exc:
        raise AuthError("lien de réinitialisation invalide ou expiré") from exc
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise AuthError("utilisateur introuvable")
    user.hashed_password = security.hash_password(new_password)
    db.commit()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def user_from_credentials(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == _normalize_email(email)).first()