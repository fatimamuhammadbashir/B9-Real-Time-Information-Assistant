"""Offline tests for the Open-Meteo weather client (no network access)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.errors import (  # noqa: E402
    APIResponseError,
    APITimeoutError,
    InputValidationError,
    LocationNotFoundError,
    UpstreamAPIError,
)
from src.weather_api import (  # noqa: E402
    CurrentWeather,
    describe_weather_code,
    geocode_city,
    get_current_weather,
    get_current_weather_for_location,
)

GEOCODE_PAYLOAD = {
    "results": [
        {
            "name": "Berlin",
            "country": "Germany",
            "admin1": "Berlin",
            "latitude": 52.52437,
            "longitude": 13.41053,
            "timezone": "Europe/Berlin",
        }
    ]
}

FORECAST_PAYLOAD = {
    "latitude": 52.52,
    "longitude": 13.41,
    "timezone": "Europe/Berlin",
    "current_units": {"temperature_2m": "C", "wind_speed_10m": "km/h"},
    "current": {
        "time": "2026-11-16T21:30",
        "temperature_2m": 8.4,
        "relative_humidity_2m": 75,
        "apparent_temperature": 4.7,
        "weather_code": 3,
        "wind_speed_10m": 16.5,
    },
}


class GeocodeTests(unittest.TestCase):
    def test_valid_city_is_resolved(self) -> None:
        with patch("src.weather_api.get_json", return_value=GEOCODE_PAYLOAD) as mocked:
            location = geocode_city("  Berlin  ")
        self.assertEqual(location.name, "Berlin")
        self.assertEqual(location.country, "Germany")
        self.assertAlmostEqual(location.latitude, 52.52437)
        self.assertEqual(mocked.call_args.kwargs["params"]["name"], "Berlin")

    def test_unknown_city_raises_location_not_found(self) -> None:
        with patch("src.weather_api.get_json", return_value={"generationtime_ms": 0.1}):
            with self.assertRaises(LocationNotFoundError):
                geocode_city("Zzzznotacity")

    def test_empty_city_raises_validation_error(self) -> None:
        for value in ("", "   ", "\t\n"):
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    geocode_city(value)

    def test_non_string_city_raises_validation_error(self) -> None:
        with self.assertRaises(InputValidationError):
            geocode_city(None)  # type: ignore[arg-type]

    def test_missing_coordinates_raise_response_error(self) -> None:
        broken = {"results": [{"name": "Berlin", "country": "Germany"}]}
        with patch("src.weather_api.get_json", return_value=broken):
            with self.assertRaises(APIResponseError):
                geocode_city("Berlin")

    def test_out_of_range_coordinates_raise_response_error(self) -> None:
        broken = {"results": [{"name": "Berlin", "latitude": 500, "longitude": 13.4}]}
        with patch("src.weather_api.get_json", return_value=broken):
            with self.assertRaises(APIResponseError):
                geocode_city("Berlin")

    def test_timeout_is_propagated(self) -> None:
        with patch("src.weather_api.get_json", side_effect=APITimeoutError("timed out")):
            with self.assertRaises(APITimeoutError):
                geocode_city("Berlin")

    def test_http_error_is_propagated(self) -> None:
        with patch(
            "src.weather_api.get_json",
            side_effect=UpstreamAPIError(503, "service unavailable"),
        ):
            with self.assertRaises(UpstreamAPIError):
                geocode_city("Berlin")


class ForecastTests(unittest.TestCase):
    def _location(self):
        with patch("src.weather_api.get_json", return_value=GEOCODE_PAYLOAD):
            return geocode_city("Berlin")

    def test_current_weather_is_parsed(self) -> None:
        location = self._location()
        with patch("src.weather_api.get_json", return_value=FORECAST_PAYLOAD):
            weather = get_current_weather_for_location(location)
        self.assertIsInstance(weather, CurrentWeather)
        self.assertAlmostEqual(weather.temperature_c, 8.4)
        self.assertAlmostEqual(weather.apparent_temperature_c, 4.7)
        self.assertAlmostEqual(weather.humidity_percent, 75.0)
        self.assertAlmostEqual(weather.wind_speed_kmh, 16.5)
        self.assertEqual(weather.condition, "Overcast")
        self.assertEqual(weather.timezone, "Europe/Berlin")
        self.assertIn("Berlin, Germany", weather.summary())
        self.assertIn("8.4 C", weather.summary())

    def test_get_current_weather_geocodes_then_forecasts(self) -> None:
        with patch(
            "src.weather_api.get_json", side_effect=[GEOCODE_PAYLOAD, FORECAST_PAYLOAD]
        ) as mocked:
            weather = get_current_weather("Berlin")
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(weather.location.name, "Berlin")

    def test_missing_current_block_raises_response_error(self) -> None:
        location = self._location()
        with patch("src.weather_api.get_json", return_value={"timezone": "Europe/Berlin"}):
            with self.assertRaises(APIResponseError):
                get_current_weather_for_location(location)

    def test_missing_temperature_raises_response_error(self) -> None:
        location = self._location()
        broken = {
            "timezone": "Europe/Berlin",
            "current": {
                "time": "2026-11-16T21:30",
                "relative_humidity_2m": 75,
                "apparent_temperature": 4.7,
                "weather_code": 3,
                "wind_speed_10m": 16.5,
            },
        }
        with patch("src.weather_api.get_json", return_value=broken):
            with self.assertRaises(APIResponseError):
                get_current_weather_for_location(location)

    def test_missing_observation_time_raises_response_error(self) -> None:
        location = self._location()
        broken = {"current": dict(FORECAST_PAYLOAD["current"], time=None)}
        with patch("src.weather_api.get_json", return_value=broken):
            with self.assertRaises(APIResponseError):
                get_current_weather_for_location(location)

    def test_weather_codes_have_readable_descriptions(self) -> None:
        self.assertEqual(describe_weather_code(0), "Clear sky")
        self.assertEqual(describe_weather_code(3), "Overcast")
        self.assertIn("Unknown", describe_weather_code(999))


if __name__ == "__main__":
    unittest.main()
