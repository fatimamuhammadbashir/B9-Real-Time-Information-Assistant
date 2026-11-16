"""Frankfurter v2 currency client.

Frankfurter publishes **reference exchange rates** sourced from the European
Central Bank. They are informational and are **not live trading quotes**.

Endpoints (free, keyless):

* https://api.frankfurter.dev/v2/rates?base=USD&quotes=EUR
* https://api.frankfurter.dev/v2/rate/USD/EUR  (single pair, unused here)

The ``/v2/rates`` endpoint returns a JSON array of objects with ``date``,
``base``, ``quote`` and ``rate`` fields. Invalid currency codes produce HTTP
422 with a JSON ``message`` such as ``invalid currency: XYZ``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from .errors import (
    APIResponseError,
    InputValidationError,
    InvalidAmountError,
    UnsupportedCurrencyError,
    UpstreamAPIError,
)
from .http_client import DEFAULT_TIMEOUT_SECONDS, get_json

RATES_URL = "https://api.frankfurter.dev/v2/rates"

REFERENCE_RATE_NOTE = (
    "Frankfurter rates are reference rates published by the European Central Bank; "
    "they are not live trading quotes."
)

_CURRENCY_PATTERN = re.compile(r"^[A-Za-z]{3}$")
_MAX_AMOUNT = 1_000_000_000.0


@dataclass(frozen=True)
class ExchangeRate:
    """A single reference rate."""

    date: str
    base: str
    quote: str
    rate: float

    def summary(self) -> str:
        date_text = self.date or "latest available date"
        return f"1 {self.base} = {self.rate:.6g} {self.quote} (reference rate, {date_text})."


@dataclass(frozen=True)
class ConversionResult:
    """A converted amount plus the reference rate that produced it."""

    amount: float
    from_currency: str
    to_currency: str
    rate: float
    converted: float
    date: str

    def summary(self) -> str:
        date_text = self.date or "latest available date"
        return (
            f"{self.amount:,.2f} {self.from_currency} = "
            f"{self.converted:,.2f} {self.to_currency} "
            f"at the reference rate {self.rate:.6g} ({date_text})."
        )


def normalize_currency_code(code: str, field: str = "Currency") -> str:
    """Validate and normalise a three-letter currency code."""

    if not isinstance(code, str):
        raise InputValidationError(f"{field} must be a three-letter code such as USD.")
    cleaned = code.strip().upper()
    if not _CURRENCY_PATTERN.fullmatch(cleaned):
        raise InputValidationError(
            f"{field} must be a three-letter code such as USD or EUR."
        )
    return cleaned


def validate_amount(amount: float | int | str) -> float:
    """Validate a positive, finite conversion amount."""

    if isinstance(amount, bool):
        raise InvalidAmountError("Amount must be a number greater than zero.")
    if isinstance(amount, str):
        text = amount.strip().replace(",", "")
        if not text:
            raise InvalidAmountError("Amount cannot be empty.")
        try:
            value = float(text)
        except ValueError as exc:
            raise InvalidAmountError("Amount must be a number greater than zero.") from exc
    elif isinstance(amount, (int, float)):
        value = float(amount)
    else:
        raise InvalidAmountError("Amount must be a number greater than zero.")

    if not math.isfinite(value):
        raise InvalidAmountError("Amount must be a finite number.")
    if value <= 0:
        raise InvalidAmountError("Amount must be greater than zero.")
    if value > _MAX_AMOUNT:
        raise InvalidAmountError("Amount is too large (maximum 1,000,000,000).")
    return value


def _positive_rate(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise APIResponseError("The currency API returned a rate that is not a number.")
    rate = float(value)
    if not math.isfinite(rate) or rate <= 0:
        raise APIResponseError("The currency API returned an invalid rate.")
    return rate


def get_exchange_rate(
    base_currency: str,
    quote_currency: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ExchangeRate:
    """Return the reference rate from ``base_currency`` to ``quote_currency``."""

    base = normalize_currency_code(base_currency, "Base currency")
    quote = normalize_currency_code(quote_currency, "Quote currency")

    if base == quote:
        return ExchangeRate(date=date.today().isoformat(), base=base, quote=quote, rate=1.0)

    try:
        payload = get_json(
            RATES_URL,
            params={"base": base, "quotes": quote},
            timeout=timeout,
        )
    except UpstreamAPIError as exc:
        if exc.status_code in {400, 404, 422}:
            detail = f" {exc.detail}" if exc.detail else ""
            raise UnsupportedCurrencyError(
                f"Unsupported currency pair {base}/{quote}.{detail}"
            ) from exc
        raise

    if not isinstance(payload, list):
        raise APIResponseError("The currency API returned an unexpected response.")
    if not payload:
        raise APIResponseError("The currency API returned no rate for this pair.")

    match: dict[str, Any] | None = None
    for entry in payload:
        if isinstance(entry, dict) and str(entry.get("quote", "")).strip().upper() == quote:
            match = entry
            break
    if match is None:
        raise APIResponseError("The currency API did not return the requested quote currency.")

    rate_value = _positive_rate(match.get("rate"))
    rate_date = match.get("date")
    return ExchangeRate(
        date=rate_date if isinstance(rate_date, str) else "",
        base=base,
        quote=quote,
        rate=rate_value,
    )


def convert_currency(
    amount: float | int | str,
    from_currency: str,
    to_currency: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ConversionResult:
    """Convert an amount using Frankfurter reference rates."""

    value = validate_amount(amount)
    source = normalize_currency_code(from_currency, "Source currency")
    target = normalize_currency_code(to_currency, "Target currency")

    if source == target:
        return ConversionResult(
            amount=value,
            from_currency=source,
            to_currency=target,
            rate=1.0,
            converted=round(value, 2),
            date=date.today().isoformat(),
        )

    exchange = get_exchange_rate(source, target, timeout=timeout)
    converted = round(value * exchange.rate, 2)
    return ConversionResult(
        amount=value,
        from_currency=source,
        to_currency=target,
        rate=exchange.rate,
        converted=converted,
        date=exchange.date,
    )
