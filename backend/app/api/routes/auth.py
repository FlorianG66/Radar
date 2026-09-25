"""Authentication & profile endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentOrg, CurrentUser, get_db, rate_limit
from app.models import User
from app.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    Message,
    OrganizationOut,
    OrganizationUpdate,
    PasswordUpdate,
    ProfileUpdate,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
    RegisterRequest,
)
from app.services import auth_service
from app.services.product_service import NotFoundError

router = APIRouter(prefix="/auth", tags=["auth"])

Db = Annotated[Session, Depends(get_db)]
LOGIN_LIMIT = Depends(rate_limit(10, 60))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Db, _: None = LOGIN_LIMIT) -> TokenResponse:
    from app.core import security

    try:
        user, _ = auth_service.register(db, payload)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TokenResponse(
        access_token=security.create_access_token(user.id, user.organization_id),
        refresh_token=security.create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Db, _: None = LOGIN_LIMIT) -> TokenResponse:
    try:
        user, access, refresh = auth_service.login(db, payload)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Db) -> TokenResponse:
    try:
        access, refresh = auth_service.refresh_tokens(db, payload.refresh_token)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout", response_model=Message)
def logout() -> Message:
    return Message(message="déconnecté")


@router.post("/verify-email", response_model=Message)
def verify_email(payload: VerifyEmailRequest, db: Db) -> Message:
    try:
        auth_service.verify_email(db, payload.token)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Message(message="email vérifié")


@router.post("/forgot-password", response_model=Message)
def forgot_password(payload: ForgotPasswordRequest, db: Db) -> Message:
    auth_service.forgot_password(db, payload.email)
    return Message(message="si ce compte existe, un email de réinitialisation a été envoyé")


@router.post("/reset-password", response_model=Message)
def reset_password(payload: ResetPasswordRequest, db: Db) -> Message:
    try:
        auth_service.reset_password(db, payload.token, payload.new_password)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Message(message="mot de passe réinitialisé, connectez-vous")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_profile(payload: ProfileUpdate, user: CurrentUser, db: Db) -> User:
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] != user.email:
        existing = db.query(User).filter(User.email == data["email"]).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cet email est déjà utilisé")
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", response_model=Message)
def update_password(payload: PasswordUpdate, user: CurrentUser, db: Db) -> Message:
    if not auth_service.security.verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mot de passe actuel incorrect")
    user.hashed_password = auth_service.security.hash_password(payload.new_password)
    db.commit()
    return Message(message="mot de passe mis à jour")


@router.get("/me/org", response_model=OrganizationOut)
def my_org(org: CurrentOrg) -> OrganizationOut:
    return OrganizationOut.model_validate(org)


@router.patch("/me/org", response_model=OrganizationOut)
def update_org(payload: OrganizationUpdate, org: CurrentOrg, db: Db) -> OrganizationOut:
    data = payload.model_dump(exclude_unset=True)
    if "settings" in data and data["settings"] is not None:
        merged = dict(org.settings or {})
        merged.update(data["settings"])
        org.settings = merged
        del data["settings"]
    for field, value in data.items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return OrganizationOut.model_validate(org)