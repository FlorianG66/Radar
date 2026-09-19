"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Radar"
    ENVIRONMENT: str = "development"
    API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    SECRET_KEY: str = "change-me"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+psycopg2://radar:radar@localhost:5432/radar"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email
    SMTP_BACKEND: str = "console"  # console | smtp
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "Radar <no-reply@radar.example>"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_BUSINESS: str = ""
    STRIPE_TRIAL_DAYS: int = 14

    # Jobs / scraping
    MAX_CONCURRENT_SCRAPES: int = 8
    SCRAPE_TIMEOUT_SECONDS: int = 30
    SCHEDULER_POLL_SECONDS: int = 30

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.STRIPE_SECRET_KEY) and not self.STRIPE_SECRET_KEY.startswith("sk_test_replace")


@lru_cache
def get_settings() -> Settings:
    return Settings()