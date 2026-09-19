"""Pydantic schemas for API requests/responses."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(default="", max_length=64)
    last_name: str = Field(default="", max_length=64)
    organization_name: str = Field(default="", max_length=128)

    @field_validator("password")
    @classmethod
    def password_rule(cls, v: str) -> str:
        if v.lower() == v and not any(c.isdigit() for c in v):
            raise ValueError("le mot de passe doit contenir une majuscule ou un chiffre")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


# ---------- Users / org ----------
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    is_admin: bool
    email_verified_at: datetime | None
    created_at: datetime


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=64)
    last_name: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    settings: dict
    created_at: datetime


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None
    settings: dict | None = None


# ---------- Plans / subscription ----------
class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str
    price_cents: int
    currency: str
    product_limit: int
    checks_per_day: int
    history_days: int
    features: list


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    current_period_end: datetime | None
    trial_ends_at: datetime | None
    plan: PlanOut | None = None
    plan_slug: str | None = None


class CheckoutRequest(BaseModel):
    plan: str  # starter | pro | business
    success_url: str | None = None
    cancel_url: str | None = None

    @field_validator("plan")
    @classmethod
    def valid_plan(cls, v: str) -> str:
        from app.core.plans import PLAN_CATALOG

        if v not in PLAN_CATALOG:
            raise ValueError("plan inconnu")
        return v


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


# ---------- Competitors ----------
class CompetitorIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class CompetitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    domain: str
    products_count: int = 0


# ---------- Products ----------
class ProductIn(BaseModel):
    url: HttpUrl
    name: str = Field(default="", max_length=255)
    competitor_id: int | None = None
    competitor_name: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=128)
    sku: str | None = Field(default=None, max_length=128)
    check_interval_hours: float | None = Field(default=None, ge=0.5, le=720)

    @field_validator("url")
    @classmethod
    def only_http(cls, v: HttpUrl) -> HttpUrl:
        if v.scheme not in ("http", "https"):
            raise ValueError("seuls les URLs http/https sont autorisés")
        return v


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    name: str
    category: str | None
    sku: str | None
    check_interval_hours: float | None
    is_active: bool
    is_scraper_enabled: bool
    last_price: float | None
    previous_price: float | None
    currency: str | None
    last_availability: str | None
    seen_promotion: bool
    last_scrape_status: str
    last_scrape_error: str | None
    last_checked_at: datetime | None
    next_check_at: datetime | None
    created_at: datetime
    variation_pct: float | None = None
    variation_abs: float | None = None
    competitor_id: int | None
    competitor_name: str | None = None
    stats: dict = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    sku: str | None = Field(default=None, max_length=128)
    competitor_id: int | None = None
    is_active: bool | None = None
    check_interval_hours: float | None = Field(default=None, ge=0.5, le=720)
    own_price: float | None = Field(default=None, ge=0)
    own_currency: str | None = None


class ProductWithOwnPriceIn(BaseModel):
    product_id: int
    own_price: float = Field(ge=0)
    own_currency: str = "EUR"
    own_name: str = Field(default="", max_length=255)


# ---------- History ----------
class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scraped_at: datetime
    price: float | None
    original_price: str | None
    currency: str | None
    previous_price: float | None
    availability: str | None
    in_promotion: bool
    stock_quantity: int | None
    shipping_cost: float | None
    product_name: str | None
    ean: str | None


class HistoryOut(BaseModel):
    product: ProductOut
    snapshots: list[SnapshotOut]
    own_prices: list[dict] = []


# ---------- Changes ----------
class ChangeEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    importance: str
    title: str
    old_state: dict | None
    new_state: dict | None
    created_at: datetime
    product_id: int
    product_name: str | None = None
    product_url: str | None = None
    competitor_name: str | None = None


class DashboardOut(BaseModel):
    products_count: int
    active_products: int
    changes_today: int
    price_drops_today: int
    price_rises_today: int
    out_of_stock_today: int
    scrape_errors: int
    plan: SubscriptionOut | None
    recent_changes: list[ChangeEventOut]
    product_preview: list[ProductOut]
    checks_today: int


# ---------- Notifications ----------
class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel: str
    status: str
    subject: str | None
    created_at: datetime
    event_type: str | None = None
    product_name: str | None = None
    read: bool = False


class NotificationPreferences(BaseModel):
    prefs: dict[str, bool]


class NotificationPrefItem(BaseModel):
    event_type: str
    enabled: bool


# ---------- CSV ----------
class CsvImportPreview(BaseModel):
    valid_rows: list[dict]
    invalid_rows: list[dict]
    errors: list[str]


class CsvImportConfirm(BaseModel):
    rows: list[dict]
    ignore_invalid: bool = True


class CsvImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


# ---------- Admin ----------
class AdminStats(BaseModel):
    users: int
    organizations: int
    products: int
    subscriptions: dict
    snapshots: int
    change_events: int
    scrape_errors: int
    queued_jobs: int
    failed_jobs: int
    domains: list[dict]
    recent_failures: list[dict]


class OrgAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    created_at: datetime
    products_count: int = 0
    users_count: int = 0
    plan_slug: str | None = None


class DomainKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    disabled: bool
    disabled_reason: str | None = None


# ---------- Misc ----------
class Message(BaseModel):
    message: str


class HealthOut(BaseModel):
    status: str
    database: str
    redis: str
    version: str = "0.1.0"