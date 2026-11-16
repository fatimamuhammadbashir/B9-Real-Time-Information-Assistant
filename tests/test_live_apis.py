"""Live integration checks for the two free public APIs.

These tests are skipped by default because they need internet access. Run them
explicitly with::

    set RUN_LIVE_TESTS=1
    .venv\\Scripts\\python.exe -m unittest tests.test_live_apis -v

They make **no OpenAI calls** and need **no API key**. If the network or either
service is unavailable, the tests fail honestly instead of being reported as
passing.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.currency_api import convert_currency, get_exchange_rate  # noqa: E402
from src.errors import LocationNotFoundError, UnsupportedCurrencyError  # noqa: E402
from src.weather_api import geocode_city, get_current_weather  # noqa: E402

RUN_LIVE = os.getenv("RUN_LIVE_TESTS") == "1"
SKIP_REASON = "set RUN_LIVE_TESTS=1 to run live public API checks"


@unittest.skipUnless(RUN_LIVE, SKIP_REASON)
class OpenMeteoLiveTests(unittest.TestCase):
    def test_geocoding_resolves_berlin(self) -> None:
        location = geocode_city("Berlin")
        self.assertEqual(location.name, "Berlin")
        self.assertEqual(location.country, "Germany")
        self.assertTrue(45.0 < location.latitude < 60.0)
        self.assertTrue(5.0 < location.longitude < 25.0)

    def test_unknown_city_returns_location_not_found(self) -> None:
        with self.assertRaises(LocationNotFoundError):
            geocode_city("Zzzznotacity")

    def test_current_weather_is_plausible(self) -> None:
        weather = get_current_weather("Berlin")
        self.assertTrue(-60.0 < weather.temperature_c < 60.0)
        self.assertTrue(0.0 <= weather.humidity_percent <= 100.0)
        self.assertGreaterEqual(weather.wind_speed_kmh, 0.0)
        self.assertTrue(weather.condition)
        self.assertTrue(weather.observed_at)
        self.assertIn("Berlin", weather.summary())


@unittest.skipUnless(RUN_LIVE, SKIP_REASON)
class FrankfurterLiveTests(unittest.TestCase):
    def test_reference_rate_usd_to_eur(self) -> None:
        rate = get_exchange_rate("USD", "EUR")
        self.assertEqual(rate.base, "USD")
        self.assertEqual(rate.quote, "EUR")
        self.assertGreater(rate.rate, 0.0)
        self.assertTrue(rate.date)

    def test_conversion_matches_returned_rate(self) -> None:
        result = convert_currency(100, "USD", "EUR")
        self.assertAlmostEqual(result.converted, round(100 * result.rate, 2), places=2)
        self.assertGreater(result.converted, 0.0)

    def test_unsupported_currency_is_reported(self) -> None:
        with self.assertRaises(UnsupportedCurrencyError):
            get_exchange_rate("USD", "ZZZ")


if __name__ == "__main__":
    unittest.main()
