"""Plan definitions used both by the backend limits and the public UI.

Everything is maintained server-side: the frontend only displays what the API
returns and the strict limits are enforced in the backend services.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    slug: str
    name: str
    price_cents: int
    currency: str
    product_limit: int
    checks_per_day: int  # minimum number of automatic checks per day
    check_interval_hours: float  # scheduled interval
    history_days: int  # 0 = unlimited
    features: tuple[str, ...] = ()
    stripe_price_id_env: str = ""


PLAN_CATALOG: dict[str, Plan] = {
    "starter": Plan(
        slug="starter",
        name="Starter",
        price_cents=3900,
        currency="EUR",
        product_limit=50,
        checks_per_day=1,
        check_interval_hours=24.0,
        history_days=30,
        features=("email_alerts",),
        stripe_price_id_env="STRIPE_PRICE_STARTER",
    ),
    "pro": Plan(
        slug="pro",
        name="Pro",
        price_cents=7900,
        currency="EUR",
        product_limit=250,
        checks_per_day=4,
        check_interval_hours=6.0,
        history_days=365,
        features=("email_alerts", "advanced_alerts", "csv_export"),
        stripe_price_id_env="STRIPE_PRICE_PRO",
    ),
    "business": Plan(
        slug="business",
        name="Business",
        price_cents=14900,
        currency="EUR",
        product_limit=1000,
        checks_per_day=24,
        check_interval_hours=1.0,
        history_days=0,  # unlimited
        features=("email_alerts", "advanced_alerts", "csv_export", "api"),
        stripe_price_id_env="STRIPE_PRICE_BUSINESS",
    ),
}

TRIAL_PLAN_SLUG = "pro"