"""Scraping subsystem: fetch → extract → normalize."""
from app.services.scraper.scraper_service import ScrapeOutcome, scrape_url
from app.services.scraper.pricetext import normalize_price

__all__ = ["ScrapeOutcome", "scrape_url", "normalize_price"]