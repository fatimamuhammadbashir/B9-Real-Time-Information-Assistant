"""Offline tests for the Frankfurter currency client (no network access)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.currency_api import (  # noqa: E402
    REFERENCE_RATE_NOTE,
    convert_currency,
    get_exchange_rate,
    normalize_currency_code,
    validate_amount,
)
from src.errors import (  # noqa: E402
    APIResponseError,
    InputValidationError,
    InvalidAmountError,
    UnsupportedCurrencyError,
    UpstreamAPIError,
)

RATES_PAYLOAD = [
    {"date": "2026-11-16", "base": "USD", "quote": "EUR", "rate": 0.90573},
]


class CurrencyCodeTests(unittest.TestCase):
    def test_codes_are_normalised(self) -> None:
        self.assertEqual(normalize_currency_code(" usd "), "USD")
        self.assertEqual(normalize_currency_code("eUr"), "EUR")

    def test_invalid_codes_are_rejected(self) -> None:
        for value in ("", "US", "USDX", "12", "U$D", None):
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    normalize_currency_code(value)  # type: ignore[arg-type]


class AmountTests(unittest.TestCase):
    def test_valid_amounts_are_accepted(self) -> None:
        self.assertEqual(validate_amount(100), 100.0)
        self.assertEqual(validate_amount(" 1,250.50 "), 1250.5)

    def test_invalid_amounts_are_rejected(self) -> None:
        for value in (0, -1, -0.01, "abc", "", True, float("nan"), float("inf"), 2_000_000_000):
            with self.subTest(value=value):
                with self.assertRaises(InvalidAmountError):
                    validate_amount(value)  # type: ignore[arg-type]


class ExchangeRateTests(unittest.TestCase):
    def test_rate_is_parsed(self) -> None:
        with patch("src.currency_api.get_json", return_value=RATES_PAYLOAD) as mocked:
            rate = get_exchange_rate("usd", "eur")
        self.assertEqual(rate.base, "USD")
        self.assertEqual(rate.quote, "EUR")
        self.assertAlmostEqual(rate.rate, 0.90573)
        self.assertEqual(rate.date, "2026-11-16")
        self.assertIn("1 USD = 0.90573 EUR", rate.summary())
        params = mocked.call_args.kwargs["params"]
        self.assertEqual(params["base"], "USD")
        self.assertEqual(params["quotes"], "EUR")

    def test_same_currency_returns_one_without_call(self) -> None:
        with patch("src.currency_api.get_json") as mocked:
            rate = get_exchange_rate("USD", "USD")
        self.assertEqual(rate.rate, 1.0)
        mocked.assert_not_called()

    def test_unsupported_currency_is_mapped_from_http_422(self) -> None:
        error = UpstreamAPIError(422, "invalid currency: XYZ")
        with patch("src.currency_api.get_json", side_effect=error):
            with self.assertRaises(UnsupportedCurrencyError) as context:
                get_exchange_rate("USD", "XYZ")
        self.assertIn("invalid currency: XYZ", str(context.exception))

    def test_server_error_is_not_mistaken_for_bad_currency(self) -> None:
        error = UpstreamAPIError(503, "service unavailable")
        with patch("src.currency_api.get_json", side_effect=error):
            with self.assertRaises(UpstreamAPIError):
                get_exchange_rate("USD", "EUR")

    def test_empty_payload_raises_response_error(self) -> None:
        with patch("src.currency_api.get_json", return_value=[]):
            with self.assertRaises(APIResponseError):
                get_exchange_rate("USD", "EUR")

    def test_mismatched_quote_raises_response_error(self) -> None:
        payload = [{"date": "2026-11-16", "base": "USD", "quote": "GBP", "rate": 0.75}]
        with patch("src.currency_api.get_json", return_value=payload):
            with self.assertRaises(APIResponseError):
                get_exchange_rate("USD", "EUR")

    def test_non_numeric_rate_raises_response_error(self) -> None:
        payload = [{"date": "2026-11-16", "base": "USD", "quote": "EUR", "rate": "n/a"}]
        with patch("src.currency_api.get_json", return_value=payload):
            with self.assertRaises(APIResponseError):
                get_exchange_rate("USD", "EUR")


class ConversionTests(unittest.TestCase):
    def test_conversion_uses_reference_rate(self) -> None:
        with patch("src.currency_api.get_json", return_value=RATES_PAYLOAD):
            result = convert_currency(100, "USD", "EUR")
        self.assertAlmostEqual(result.rate, 0.90573)
        self.assertAlmostEqual(result.converted, 90.57)
        self.assertIn("100.00 USD = 90.57 EUR", result.summary())
        self.assertIn("reference rate", result.summary())

    def test_same_currency_conversion_is_identity(self) -> None:
        with patch("src.currency_api.get_json") as mocked:
            result = convert_currency(25, "GBP", "GBP")
        self.assertEqual(result.rate, 1.0)
        self.assertAlmostEqual(result.converted, 25.0)
        mocked.assert_not_called()

    def test_invalid_amount_is_rejected_before_network(self) -> None:
        with patch("src.currency_api.get_json") as mocked:
            with self.assertRaises(InvalidAmountError):
                convert_currency(-5, "USD", "EUR")
        mocked.assert_not_called()

    def test_reference_note_is_explicit(self) -> None:
        self.assertIn("not live trading quotes", REFERENCE_RATE_NOTE)


if __name__ == "__main__":
    unittest.main()
