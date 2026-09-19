"""Price/currency normalization.

Turns messy human price strings into (value, currency_iso) pairs.

Examples handled:
    649,99 €      -> 649.99 EUR
    649.99 EUR    -> 649.99 EUR
    649 €         -> 649.0 EUR
    $1,299.99     -> 1299.99 USD
    12 900 FCFA   -> 12900.0 XOF
    Prix : 599,00 € TTC -> 599.0 EUR
"""
from __future__ import annotations

import re

CURRENCY_SYMBOLS: dict[str, str] = {
    "€": "EUR",
    "EUR": "EUR",
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "£": "GBP",
    "GBP": "GBP",
    "CHF": "CHF",
    "C$": "CAD",
    "CAD": "CAD",
    "FCFA": "XOF",
    "XOF": "XOF",
    "MAD": "MAD",
    "DH": "MAD",
    "XPF": "XPF",
    "CDF": "CDF",
    "¥": "JPY",
    "JPY": "JPY",
    "CNY": "CNY",
    "RMB": "CNY",
    "kr": "SEK",
    "SEK": "SEK",
    "zł": "PLN",
    "PLN": "PLN",
}

# Symbols that may appear immediately next to digits without a space.
_SYMBOL_PREFIX = ("$", "£", "¥", "€", "US$")
_DEFAULT_CURRENCY = "EUR"

_NUMBER_RE = re.compile(r"[+-]?\d[\d\s\u00a0.,]*(?:[.,]\d+)?")
_CURRENCY_RE = re.compile(
    r"(EUR|EUR|US\$|USD|GBP|CHF|CAD|FCFA|XOF|MAD|DH|XPF|CDF|JPY|CNY|RMB|SEK|PLN|zł|kr|€|\$|£|¥)",
    re.IGNORECASE,
)


def detect_currency(text: str) -> str | None:
    """Return ISO code if a currency symbol/code is present, else None."""
    matches = _CURRENCY_RE.findall(text)
    for match in matches:
        key = match.strip()
        if key.upper() in CURRENCY_SYMBOLS:
            return CURRENCY_SYMBOLS[key.upper()]
        if key in CURRENCY_SYMBOLS:
            return CURRENCY_SYMBOLS[key]
    return None


def _clean_number(token: str) -> str:
    return token.replace("\u00a0", "").replace(" ", "").replace(",", " ").replace(".", " ").strip()


def parse_number(text: str) -> float | None:
    """Parse the numeric value out of a price fragment.

    Heuristics for ambiguous separators:
    - if both a comma and a dot appear, the *last* one is the decimal separator
      (handles 1.299,99 and 1,299.99);
    - with a single separator, 1 or 2 trailing digits => decimal separator,
      otherwise it is a thousands separator (1.099 -> 1099).
    """
    text = text.replace("\u00a0", " ")
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    s = match.group(0).strip().replace(" ", "")

    def _groups(sep: str) -> list[str]:
        return s.split(sep)

    has_comma = "," in s
    has_dot = "." in s
    if has_comma and has_dot:
        # The last separator is the decimal one.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        parts = _groups(",")
        if len(parts) >= 2 and 0 < len(parts[-1]) <= 2 and parts[-1].isdigit():
            s = "".join(parts[:-1]) + "." + parts[-1]
        else:
            s = s.replace(",", "")
    elif has_dot:
        parts = _groups(".")
        if len(parts) >= 2 and 0 < len(parts[-1]) <= 2 and parts[-1].isdigit():
            s = "".join(parts[:-1]) + "." + parts[-1]
        else:
            s = s.replace(".", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def normalize_price(text: str, default_currency: str | None = None) -> tuple[float | None, str | None]:
    """Return (value, currency_iso) from a raw price string.

    ``value`` may be None when nothing numeric can be found.
    """
    if not text:
        return None, None
    currency = detect_currency(text) or default_currency or _DEFAULT_CURRENCY
    value = parse_number(text)
    return value, currency


def format_price(value: float | None, currency: str | None) -> str:
    """Human friendly display, e.g. 649.99 EUR -> '649,99 €'."""
    if value is None:
        return "—"
    symbols = {v: k for k, v in CURRENCY_SYMBOLS.items() if len(k) == 1 or k in ("FCFA", "US$", "zł")}
    localized = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    sym = symbols.get(currency, currency or "")
    if sym and len(sym) <= 2:
        return f"{localized} {sym}" if currency else f"{localized} {sym}"
    return f"{localized} {sym}"