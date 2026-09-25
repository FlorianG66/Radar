"""Price/currency normalization units."""
from app.services.scraper.pricetext import detect_currency, normalize_price, parse_number, format_price


class TestParseNumber:
    def test_european_comma(self):
        assert parse_number("649,99") == 649.99
        assert parse_number("649,00") == 649.0

    def test_european_dot_thousands(self):
        assert parse_number("1.299,99") == 1299.99

    def test_us_format(self):
        assert parse_number("1,299.99") == 1299.99
        assert parse_number("649.99") == 649.99

    def test_thousands_no_decimal(self):
        assert parse_number("12,345") == 12345
        assert parse_number("1.099") == 1099

    def test_spaces(self):
        assert parse_number("12 900") == 12900

    def test_int(self):
        assert parse_number("649") == 649.0

    def test_nan(self):
        assert parse_number("aucun prix") is None

    def test_nbsp(self):
        assert parse_number("1\u00a0499,50") == 1499.5

    def test_decimal_only_one_digit(self):
        assert parse_number("1,2") == 1.2


class TestDetectCurrency:
    def test_euro_symbol(self):
        assert detect_currency("649,99 €") == "EUR"

    def test_usd(self):
        assert detect_currency("$1,299") == "USD"
        assert detect_currency("99.99 USD") == "USD"

    def test_fcfa(self):
        assert detect_currency("12 900 FCFA") == "XOF"

    def test_gbp(self):
        assert detect_currency("£99") == "GBP"

    def test_none(self):
        assert detect_currency("649,99") is None


class TestNormalizePrice:
    def test_full(self):
        assert normalize_price("649,99 €") == (649.99, "EUR")

    def test_default_currency(self):
        assert normalize_price("649") == (649.0, "EUR")

    def test_explicit_currency(self):
        assert normalize_price("1299.99 EUR") == (1299.99, "EUR")

    def test_none(self):
        assert normalize_price("") == (None, None)
        assert normalize_price(None) == (None, None)


class TestFormatPrice:
    def test_fr(self):
        assert "€" in format_price(649.99, "EUR")
        assert format_price(649.99, "EUR").startswith("649,99")