"""SQLAlchemy ORM models — the full Radar data schema.

Design notes:
- Integer primary keys for simplicity and portability.
- Prices stored as NUMERIC(12,2) plus the original string representation
  and the ISO currency code (forward-compatible with multi-currency).
- Snapshots are immutable (append-only); the change engine reads the two
  last snapshots of a product to emit ChangeEvents.
- ScrapeJob is intentionally separated from snapshots so that a failed
  scrape is logged and never interpreted as a price change.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    product_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    checks_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    check_interval_hours: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    history_days: Mapped[int] = mapped_column(Integer, default=30)
    features: Mapped[list] = mapped_column(JSON, default=list)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    products: Mapped[list["Product"]] = relationship(back_populates="organization")
    competitors: Mapped[list["Competitor"]] = relationship(back_populates="organization")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="organization")
    change_events: Mapped[list["ChangeEvent"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(64), default="")
    last_name: Mapped[str] = mapped_column(String(64), default="")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    organization: Mapped["Organization | None"] = relationship(back_populates="users")
    notification_preferences: Mapped[list["NotificationPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="trialing", index=True)  # trialing|active|past_due|canceled|incomplete
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), index=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")


class Competitor(Base):
    __tablename__ = "competitors"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_competitor_org_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="competitors")
    products: Mapped[list["Product"]] = relationship(back_populates="competitor")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("organization_id", "url", name="uq_product_org_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    competitor_id: Mapped[int | None] = mapped_column(ForeignKey("competitors.id"), index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str | None] = mapped_column(String(128))
    sku: Mapped[str | None] = mapped_column(String(128))
    check_interval_hours: Mapped[float | None] = mapped_column(Numeric(6, 2))
    is_scraper_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Latest known values (denormalized for quick display)
    last_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    previous_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    last_availability: Mapped[str | None] = mapped_column(String(16))
    seen_promotion: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scrape_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|ok|error|disabled
    last_scrape_error: Mapped[str | None] = mapped_column(String(255))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # Client's own price for the comparison view (optional manual entry)
    own_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    own_currency: Mapped[str] = mapped_column(String(3), default="EUR")
    own_name: Mapped[str] = mapped_column(String(255), default="")
    own_price_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="products")
    competitor: Mapped["Competitor | None"] = relationship(back_populates="products")
    snapshots: Mapped[list["ProductSnapshot"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductSnapshot.scraped_at.desc()"
    )
    change_events: Mapped[list["ChangeEvent"]] = relationship(back_populates="product")
    scrape_jobs: Mapped[list["ScrapeJob"]] = relationship(back_populates="product")


class ProductSnapshot(Base):
    """One successful fetch of a product page, append-only."""

    __tablename__ = "product_snapshots"
    __table_args__ = (
        Index("ix_snapshots_product_time", "product_id", "scraped_at"),
        Index("ix_snapshots_time", "scraped_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Price (normalized) + original representation + currency
    price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    original_price: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(3))
    previous_price: Mapped[float | None] = mapped_column(Numeric(12, 2))  # strike-through ("old") price
    original_previous_price: Mapped[str | None] = mapped_column(String(64))

    availability: Mapped[str | None] = mapped_column(String(16))  # in_stock|out_of_stock|preorder
    stock_quantity: Mapped[int | None] = mapped_column(Integer)
    in_promotion: Mapped[bool] = mapped_column(Boolean, default=False)
    shipping_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    shipping_currency: Mapped[str | None] = mapped_column(String(3))

    product_name: Mapped[str | None] = mapped_column(String(255))
    product_sku: Mapped[str | None] = mapped_column(String(128))
    ean: Mapped[str | None] = mapped_column(String(32))
    image_url: Mapped[str | None] = mapped_column(Text)

    raw_data: Mapped[dict | None] = mapped_column(JSON)

    product: Mapped["Product"] = relationship(back_populates="snapshots")


class ChangeEvent(Base):
    __tablename__ = "change_events"
    __table_args__ = (
        Index("ix_change_events_org_time", "organization_id", "created_at"),
        Index("ix_change_events_product_time", "product_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # price_drop|price_rise|out_of_stock|in_stock|promotion_start|promotion_end|promotion_change|product_info
    importance: Mapped[str] = mapped_column(String(8), nullable=False)  # high|medium|low
    old_state: Mapped[dict | None] = mapped_column(JSON)
    new_state: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped["Organization"] = relationship(back_populates="change_events")
    product: Mapped["Product"] = relationship(back_populates="change_events")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="event")

    @property
    def title(self) -> str:
        return CHANGE_EVENT_TITLES.get(self.event_type, self.event_type.replace("_", " "))


CHANGE_EVENT_TITLES = {
    "price_drop": "Baisse de prix",
    "price_rise": "Hausse de prix",
    "price_back": "Retour à un prix précédent",
    "out_of_stock": "Passage en rupture",
    "in_stock": "Retour en stock",
    "promotion_start": "Promotion détectée",
    "promotion_end": "Fin de promotion",
    "promotion_change": "Promotion modifiée",
    "product_info": "Informations produit modifiées",
    "scrape_failed": "Erreur de surveillance",
}

IMPORTANCE = {
    "price_drop": "high",
    "price_rise": "medium",
    "price_back": "medium",
    "out_of_stock": "medium",
    "in_stock": "low",
    "promotion_start": "high",
    "promotion_end": "medium",
    "promotion_change": "low",
    "product_info": "low",
    "scrape_failed": "low",
}


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_time", "user_id", "created_at"),
        Index("ix_notifications_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("change_events.id"), index=True)
    channel: Mapped[str] = mapped_column(String(16), default="email")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|sent|failed|suppressed
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    event: Mapped["ChangeEvent | None"] = relationship(back_populates="notifications")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "event_type", name="uq_notif_pref_user_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="notification_preferences")


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"
    __table_args__ = (
        Index("ix_scrape_jobs_status", "status"),
        Index("ix_scrape_jobs_product_status", "product_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|success|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(255))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    rq_job_id: Mapped[str | None] = mapped_column(String(64), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped["Product"] = relationship(back_populates="scrape_jobs")


class DomainState(Base):
    """Per-domain scraper controls (admin can temporarily disable a domain)."""

    __tablename__ = "domain_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled_reason: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)