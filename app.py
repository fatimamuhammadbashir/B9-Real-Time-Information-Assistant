"""Command-line entry point for the B9 Real-Time Information Assistant.

Usage examples::

    python app.py "What is the weather in Berlin?"
    python app.py                      # interactive live mode
    python app.py --offline            # five simulated-routing examples
    python app.py --check-apis         # live checks for Open-Meteo and Frankfurter

The live modes need OPENAI_API_KEY. The offline demo and the public API checks
do not: they use FakeListChatModel for routing (clearly labelled) and the free,
keyless Open-Meteo and Frankfurter APIs for data.
"""

from __future__ import annotations

import argparse
import sys

from langchain_core.language_models import FakeListChatModel

from src.assistant import answer_question, create_chat_model, get_settings
from src.currency_api import REFERENCE_RATE_NOTE, convert_currency, get_exchange_rate
from src.errors import AssistantError, MissingAPIKeyError
from src.weather_api import geocode_city, get_current_weather

OFFLINE_CASES: list[tuple[str, str]] = [
    (
        "What is the weather in Berlin right now?",
        '{"tool": "current_weather", "arguments": {"city": "Berlin"}}',
    ),
    (
        "Do I need an umbrella in Tokyo? What is the weather there?",
        '{"tool": "current_weather", "arguments": {"city": "Tokyo"}}',
    ),
    (
        "How much is 100 USD in EUR?",
        '{"tool": "convert_currency", "arguments": {"amount": 100, "from_currency": "USD", "to_currency": "EUR"}}',
    ),
    (
        "What is the exchange rate from GBP to JPY?",
        '{"tool": "exchange_rate", "arguments": {"base_currency": "GBP", "quote_currency": "JPY"}}',
    ),
    (
        "Convert 250 EUR to INR.",
        '{"tool": "convert_currency", "arguments": {"amount": 250, "from_currency": "EUR", "to_currency": "INR"}}',
    ),
]


def run_offline_demo() -> int:
    """Run five examples with simulated LLM routing and live public API data."""

    print("OFFLINE ROUTING DEMO")
    print("LLM routing: FakeListChatModel (simulated, not a live OpenAI response).")
    print("Weather and currency data: free Open-Meteo and Frankfurter APIs.")
    print("=" * 70)

    failures = 0
    for index, (question, response) in enumerate(OFFLINE_CASES, start=1):
        llm = FakeListChatModel(responses=[response])
        print(f"\nQ{index}: {question}")
        try:
            answer = answer_question(question, llm, simulated=True)
            print(f"A{index}: {answer.render()}")
        except AssistantError as exc:
            print(f"A{index}: [SIMULATION] Demo failed: {exc}")
            failures += 1
    return 1 if failures else 0


def run_live_question(question: str) -> int:
    settings = get_settings()
    try:
        llm = create_chat_model()
    except MissingAPIKeyError as exc:
        print(f"Cannot start live mode: {exc}")
        return 2

    print(f"Live OpenAI routing with model '{settings.model}'. Key is configured.")
    answer = answer_question(question, llm)
    print(answer.render())
    return 0 if not answer.error else 1


def run_interactive() -> int:
    settings = get_settings()
    try:
        llm = create_chat_model()
    except MissingAPIKeyError as exc:
        print(f"Cannot start live mode: {exc}")
        return 2

    print("Real-Time Information Assistant")
    print(f"Model: {settings.model}")
    print("Type 'quit' or 'exit' to stop.")
    while True:
        try:
            question = input("\nYour question: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if question.strip().lower() in {"quit", "exit"}:
            return 0
        if not question.strip():
            print("Please enter a question.")
            continue
        answer = answer_question(question, llm)
        print(answer.render())


def check_apis() -> int:
    """Run live checks against both free public APIs."""

    failures = 0

    try:
        location = geocode_city("Berlin")
        print(f"PASS Open-Meteo geocoding: {location.label()} "
              f"({location.latitude:.4f}, {location.longitude:.4f})")
    except Exception as exc:  # noqa: BLE001 - report the real failure
        print(f"FAIL Open-Meteo geocoding: {exc}")
        failures += 1

    try:
        weather = get_current_weather("Berlin")
        print(f"PASS Open-Meteo forecast: {weather.summary()}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL Open-Meteo forecast: {exc}")
        failures += 1

    try:
        rate = get_exchange_rate("USD", "EUR")
        print(f"PASS Frankfurter rates: {rate.summary()}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL Frankfurter rates: {exc}")
        failures += 1

    try:
        conversion = convert_currency(100, "USD", "EUR")
        expected = round(conversion.amount * conversion.rate, 2)
        if abs(conversion.converted - expected) > 0.01:
            raise AssertionError(
                f"conversion {conversion.converted} does not match rate {expected}"
            )
        if conversion.converted <= 0:
            raise AssertionError("conversion result must be positive")
        print(f"PASS Frankfurter conversion: {conversion.summary()}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL Frankfurter conversion: {exc}")
        failures += 1

    print(f"\nReference-rate notice: {REFERENCE_RATE_NOTE}")
    print("Live public API checks failed:", failures)
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Real-Time Information Assistant (B9 API Integration)."
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Ask one question in live mode. Omit for an interactive session.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run five examples with FakeListChatModel routing (no OpenAI key).",
    )
    parser.add_argument(
        "--check-apis",
        action="store_true",
        help="Run live checks against Open-Meteo and Frankfurter (no OpenAI key).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.offline:
        return run_offline_demo()
    if args.check_apis:
        return check_apis()
    if args.question:
        return run_live_question(args.question)
    return run_interactive()


if __name__ == "__main__":
    sys.exit(main())
