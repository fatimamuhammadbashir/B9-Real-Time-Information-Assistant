"""LangChain tool definitions for the Real-Time Information Assistant.

Three tools are exposed:

* ``current_weather``  - Open-Meteo geocoding + current conditions
* ``exchange_rate``    - Frankfurter reference rate for one currency pair
* ``convert_currency`` - Frankfurter conversion of an amount

Tool functions never raise for expected input or API problems: they return a
short, user-safe message instead, so a language model can relay it to the user.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from .currency_api import REFERENCE_RATE_NOTE
from .currency_api import convert_currency as convert_currency_api
from .currency_api import get_exchange_rate
from .errors import AssistantError
from .weather_api import get_current_weather


class WeatherInput(BaseModel):
    """Input schema for the weather tool."""

    city: str = Field(
        description="City name in plain language, for example 'Berlin' or 'New York'."
    )


class ExchangeRateInput(BaseModel):
    """Input schema for the exchange-rate tool."""

    base_currency: str = Field(description="Three-letter source currency code, for example USD.")
    quote_currency: str = Field(description="Three-letter target currency code, for example EUR.")


class ConvertCurrencyInput(BaseModel):
    """Input schema for the currency-conversion tool."""

    amount: float = Field(description="Positive amount to convert, for example 100.")
    from_currency: str = Field(description="Three-letter source currency code, for example USD.")
    to_currency: str = Field(description="Three-letter target currency code, for example EUR.")


@tool("current_weather", args_schema=WeatherInput)
def current_weather_tool(city: str) -> str:
    """Get the current weather for a city using Open-Meteo.

    Use this for questions about present temperature, conditions, humidity or
    wind in a named place. The city is resolved with the Open-Meteo geocoding
    API first.
    """

    try:
        weather = get_current_weather(city)
        return weather.summary()
    except AssistantError as exc:
        return f"Weather lookup failed: {exc}"


@tool("exchange_rate", args_schema=ExchangeRateInput)
def exchange_rate_tool(base_currency: str, quote_currency: str) -> str:
    """Get the Frankfurter reference exchange rate for one currency pair.

    Use this when the user asks 'what is the rate' or 'how many EUR is one USD'
    without asking to convert a specific amount. Codes must be three letters,
    such as USD, EUR, GBP or JPY.
    """

    try:
        rate = get_exchange_rate(base_currency, quote_currency)
        return f"{rate.summary()} {REFERENCE_RATE_NOTE}"
    except AssistantError as exc:
        return f"Exchange-rate lookup failed: {exc}"


@tool("convert_currency", args_schema=ConvertCurrencyInput)
def convert_currency_tool(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert a specific amount between two currencies using Frankfurter.

    Use this when the user supplies an amount to convert, for example
    'How much is 250 EUR in INR?'. Codes must be three letters.
    """

    try:
        result = convert_currency_api(amount, from_currency, to_currency)
        return f"{result.summary()} {REFERENCE_RATE_NOTE}"
    except AssistantError as exc:
        return f"Currency conversion failed: {exc}"


ALL_TOOLS: list[BaseTool] = [
    current_weather_tool,
    exchange_rate_tool,
    convert_currency_tool,
]

TOOL_BY_NAME: dict[str, BaseTool] = {item.name: item for item in ALL_TOOLS}


def get_tool(name: str) -> BaseTool:
    """Return a tool by name, raising a clear error for unknown names."""

    try:
        return TOOL_BY_NAME[name]
    except KeyError as exc:
        available = ", ".join(sorted(TOOL_BY_NAME))
        raise KeyError(f"Unknown tool '{name}'. Available tools: {available}.") from exc
