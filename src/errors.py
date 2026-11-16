"""Domain exceptions for the B9 Real-Time Information Assistant.

Every exception is safe to show to a user: messages never include API keys,
request headers, or raw upstream response bodies beyond a short error detail.
"""

from __future__ import annotations


class AssistantError(Exception):
    """Base class for all project errors."""


class InputValidationError(AssistantError):
    """Raised when a user-supplied value is missing or malformed."""


class ConfigurationError(AssistantError):
    """Raised when required local configuration is missing."""


class MissingAPIKeyError(ConfigurationError):
    """Raised when OPENAI_API_KEY is not configured."""


class APIConnectionError(AssistantError):
    """Raised when a public API cannot be reached."""


class APITimeoutError(APIConnectionError):
    """Raised when a public API request times out."""


class UpstreamAPIError(AssistantError):
    """Raised when a public API returns a non-success HTTP status."""

    def __init__(self, status_code: int, message: str = "") -> None:
        self.status_code = status_code
        self.detail = (message or "").strip()
        text = f"HTTP {status_code}"
        if self.detail:
            text = f"{text}: {self.detail}"
        super().__init__(text)


class APIResponseError(AssistantError):
    """Raised when a public API returns malformed or unexpected JSON."""


class LocationNotFoundError(AssistantError):
    """Raised when the geocoding API cannot find a city."""


class CurrencyError(AssistantError):
    """Base class for currency-related errors."""


class UnsupportedCurrencyError(CurrencyError):
    """Raised when a currency code is not supported by Frankfurter."""


class InvalidAmountError(CurrencyError):
    """Raised when a conversion amount is invalid."""
