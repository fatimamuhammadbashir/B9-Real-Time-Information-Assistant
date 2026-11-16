"""Offline tests for the LangChain tool wrappers (no network access)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.currency_api import ConversionResult, ExchangeRate  # noqa: E402
from src.errors import LocationNotFoundError, UnsupportedCurrencyError  # noqa: E402
from src.tools import (  # noqa: E402
    ALL_TOOLS,
    convert_currency_tool,
    current_weather_tool,
    exchange_rate_tool,
    get_tool,
)
from src.weather_api import CurrentWeather, Location  # noqa: E402

LOCATION = Location(
    name="Berlin",
    country="Germany",
    latitude=52.52,
    longitude=13.41,
    timezone="Europe/Berlin",
)
WEATHER = CurrentWeather(
    location=LOCATION,
    temperature_c=8.4,
    apparent_temperature_c=4.7,
    humidity_percent=75.0,
    wind_speed_kmh=16.5,
    weather_code=3,
    condition="Overcast",
    observed_at="2026-11-16T21:30",
    timezone="Europe/Berlin",
)
RATE = ExchangeRate(date="2026-11-16", base="USD", quote="EUR", rate=0.90573)
CONVERSION = ConversionResult(
    amount=100.0,
    from_currency="USD",
    to_currency="EUR",
    rate=0.90573,
    converted=90.57,
    date="2026-11-16",
)


class ToolRegistrationTests(unittest.TestCase):
    def test_expected_tools_are_registered(self) -> None:
        self.assertEqual(
            sorted(tool.name for tool in ALL_TOOLS),
            ["convert_currency", "current_weather", "exchange_rate"],
        )

    def test_descriptions_are_present(self) -> None:
        for item in ALL_TOOLS:
            with self.subTest(tool=item.name):
                self.assertTrue(item.description)
                self.assertGreater(len(item.description or ""), 20)

    def test_weather_schema_requires_city(self) -> None:
        self.assertIn("city", current_weather_tool.args)

    def test_conversion_schema_exposes_expected_fields(self) -> None:
        self.assertEqual(
            set(convert_currency_tool.args),
            {"amount", "from_currency", "to_currency"},
        )

    def test_get_tool_returns_registered_tool(self) -> None:
        self.assertIs(get_tool("current_weather"), current_weather_tool)

    def test_get_tool_rejects_unknown_name(self) -> None:
        with self.assertRaises(KeyError):
            get_tool("stock_price")


class WeatherToolTests(unittest.TestCase):
    def test_returns_readable_weather(self) -> None:
        with patch("src.tools.get_current_weather", return_value=WEATHER):
            output = current_weather_tool.invoke({"city": "Berlin"})
        self.assertIn("Berlin, Germany", output)
        self.assertIn("8.4 C", output)
        self.assertIn("overcast", output.lower())

    def test_unknown_city_becomes_friendly_message(self) -> None:
        with patch(
            "src.tools.get_current_weather",
            side_effect=LocationNotFoundError("No location found for 'Atlantis'."),
        ):
            output = current_weather_tool.invoke({"city": "Atlantis"})
        self.assertIn("Weather lookup failed", output)
        self.assertIn("Atlantis", output)


class CurrencyToolTests(unittest.TestCase):
    def test_exchange_rate_includes_disclaimer(self) -> None:
        with patch("src.tools.get_exchange_rate", return_value=RATE):
            output = exchange_rate_tool.invoke(
                {"base_currency": "USD", "quote_currency": "EUR"}
            )
        self.assertIn("1 USD = 0.90573 EUR", output)
        self.assertIn("not live trading quotes", output)

    def test_conversion_includes_disclaimer(self) -> None:
        with patch("src.tools.convert_currency_api", return_value=CONVERSION):
            output = convert_currency_tool.invoke(
                {"amount": 100, "from_currency": "USD", "to_currency": "EUR"}
            )
        self.assertIn("100.00 USD = 90.57 EUR", output)
        self.assertIn("reference rate", output)
        self.assertIn("not live trading quotes", output)

    def test_unsupported_currency_becomes_friendly_message(self) -> None:
        with patch(
            "src.tools.get_exchange_rate",
            side_effect=UnsupportedCurrencyError("Unsupported currency pair USD/XYZ."),
        ):
            output = exchange_rate_tool.invoke(
                {"base_currency": "USD", "quote_currency": "XYZ"}
            )
        self.assertIn("Exchange-rate lookup failed", output)
        self.assertIn("USD/XYZ", output)

    def test_conversion_error_becomes_friendly_message(self) -> None:
        with patch(
            "src.tools.convert_currency_api",
            side_effect=UnsupportedCurrencyError("Unsupported currency pair EUR/XYZ."),
        ):
            output = convert_currency_tool.invoke(
                {"amount": 10, "from_currency": "EUR", "to_currency": "XYZ"}
            )
        self.assertIn("Currency conversion failed", output)


if __name__ == "__main__":
    unittest.main()
