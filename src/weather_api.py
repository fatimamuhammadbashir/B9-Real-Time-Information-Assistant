"""Open-Meteo weather client.

Two free, keyless endpoints are used:

* geocoding: https://geocoding-api.open-meteo.com/v1/search
* forecast:  https://api.open-meteo.com/v1/forecast

The forecast endpoint is asked for ``current`` conditions only. No API key is
required, and no credentials are sent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import (
    APIResponseError,
    InputValidationError,
    LocationNotFoundError,
)
from .http_client import DEFAULT_TIMEOUT_SECONDS, get_json

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

CURRENT_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "weather_code",
    "wind_speed_10m",
)

# WMO weather interpretation codes used by Open-Meteo.
WMO_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code: int) -> str:
    """Return a human-readable description for a WMO weather code."""

    return WMO_WEATHER_CODES.get(code, f"Unknown weather code ({code})")


@dataclass(frozen=True)
class Location:
    """A resolved place returned by the geocoding endpoint."""

    name: str
    country: str
    latitude: float
    longitude: float
    timezone: str | None = None
    admin1: str | None = None

    def label(self) -> str:
        parts = [self.name]
        if self.admin1 and self.admin1.lower() != self.name.lower():
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass(frozen=True)
class CurrentWeather:
    """Current conditions for a resolved location."""

    location: Location
    temperature_c: float
    apparent_temperature_c: float
    humidity_percent: float
    wind_speed_kmh: float
    weather_code: int
    condition: str
    observed_at: str
    timezone: str

    def summary(self) -> str:
        return (
            f"{self.location.label()}: {self.temperature_c:.1f} C "
            f"(feels like {self.apparent_temperature_c:.1f} C), "
            f"{self.condition.lower()}; humidity {self.humidity_percent:.0f}%; "
            f"wind {self.wind_speed_kmh:.1f} km/h; "
            f"observed {self.observed_at}"
            + (f" ({self.timezone})." if self.timezone else ".")
        )


def _clean_city(city: str) -> str:
    if not isinstance(city, str):
        raise InputValidationError("City must be provided as text.")
    cleaned = " ".join(city.split())
    if not cleaned:
        raise InputValidationError("City name cannot be empty.")
    if len(cleaned) > 100:
        raise InputValidationError("City name is too long (maximum 100 characters).")
    return cleaned


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise APIResponseError(f"The weather response is missing a valid '{field}' value.")
    return float(value)


def geocode_city(city: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Location:
    """Resolve a city name to coordinates using the Open-Meteo geocoding API."""

    cleaned = _clean_city(city)
    payload = get_json(
        GEOCODING_URL,
        params={"name": cleaned, "count": 1, "language": "en", "format": "json"},
        timeout=timeout,
    )
    if not isinstance(payload, dict):
        raise APIResponseError("The geocoding API returned an unexpected response.")

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise LocationNotFoundError(f"No location found for '{cleaned}'.")

    first = results[0]
    if not isinstance(first, dict):
        raise APIResponseError("The geocoding API returned an invalid result.")

    name = first.get("name")
    if not isinstance(name, str) or not name.strip():
        raise APIResponseError("The geocoding result is missing a city name.")

    latitude = _number(first.get("latitude"), "latitude")
    longitude = _number(first.get("longitude"), "longitude")
    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        raise APIResponseError("The geocoding result contains out-of-range coordinates.")

    country = first.get("country")
    timezone = first.get("timezone")
    admin1 = first.get("admin1")

    return Location(
        name=name.strip(),
        country=country.strip() if isinstance(country, str) else "",
        latitude=latitude,
        longitude=longitude,
        timezone=timezone if isinstance(timezone, str) else None,
        admin1=admin1 if isinstance(admin1, str) else None,
    )


def get_current_weather_for_location(
    location: Location, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> CurrentWeather:
    """Fetch current conditions for already-resolved coordinates."""

    payload = get_json(
        FORECAST_URL,
        params={
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": ",".join(CURRENT_FIELDS),
            "timezone": "auto",
        },
        timeout=timeout,
    )
    if not isinstance(payload, dict):
        raise APIResponseError("The forecast API returned an unexpected response.")

    current = payload.get("current")
    if not isinstance(current, dict):
        raise APIResponseError("The forecast response is missing current conditions.")

    temperature = _number(current.get("temperature_2m"), "temperature_2m")
    apparent = _number(current.get("apparent_temperature"), "apparent_temperature")
    humidity = _number(current.get("relative_humidity_2m"), "relative_humidity_2m")
    wind = _number(current.get("wind_speed_10m"), "wind_speed_10m")
    code_value = current.get("weather_code")
    if isinstance(code_value, bool) or not isinstance(code_value, (int, float)):
        raise APIResponseError("The forecast response is missing a valid weather_code.")

    observed_at = current.get("time")
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise APIResponseError("The forecast response is missing an observation time.")

    timezone = payload.get("timezone")
    timezone_text = timezone if isinstance(timezone, str) else (location.timezone or "")

    return CurrentWeather(
        location=location,
        temperature_c=temperature,
        apparent_temperature_c=apparent,
        humidity_percent=humidity,
        wind_speed_kmh=wind,
        weather_code=int(code_value),
        condition=describe_weather_code(int(code_value)),
        observed_at=observed_at,
        timezone=timezone_text,
    )


def get_current_weather(city: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> CurrentWeather:
    """Resolve a city and return its current weather."""

    location = geocode_city(city, timeout=timeout)
    return get_current_weather_for_location(location, timeout=timeout)
