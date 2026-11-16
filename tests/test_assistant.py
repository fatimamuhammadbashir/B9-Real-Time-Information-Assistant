"""Offline tests for the LangChain routing assistant.

No OpenAI API call is made. ``FakeListChatModel`` supplies canned routing JSON,
and tool execution is mocked or replaced with a small local tool.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.language_models import FakeListChatModel  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.assistant import (  # noqa: E402
    DEFAULT_MODEL,
    answer_question,
    create_chat_model,
    parse_decision,
    select_tool,
)
from src.errors import (  # noqa: E402
    AssistantError,
    InputValidationError,
    MissingAPIKeyError,
)


class StrictInput(BaseModel):
    amount: int


@tool("strict_tool", args_schema=StrictInput)
def strict_tool(amount: int) -> str:
    """A local test tool that requires an integer amount."""

    return f"strict result: {amount}"


class FakeWeatherInput(BaseModel):
    city: str


@tool("current_weather", args_schema=FakeWeatherInput)
def fake_weather(city: str) -> str:
    """A local fake weather tool used only by the offline tests."""

    return f"Fake weather for {city}: 1.0 C, clear."


class SelectToolTests(unittest.TestCase):
    def test_selects_weather_for_a_weather_question(self) -> None:
        llm = FakeListChatModel(
            responses=['{"tool": "current_weather", "arguments": {"city": "Berlin"}}']
        )
        decision = select_tool("What is the weather in Berlin?", llm)
        self.assertEqual(decision.tool_name, "current_weather")
        self.assertEqual(decision.arguments, {"city": "Berlin"})

    def test_selects_conversion_for_an_amount_question(self) -> None:
        llm = FakeListChatModel(
            responses=[
                '{"tool": "convert_currency", "arguments": '
                '{"amount": 100, "from_currency": "USD", "to_currency": "EUR"}}'
            ]
        )
        decision = select_tool("How much is 100 USD in EUR?", llm)
        self.assertEqual(decision.tool_name, "convert_currency")
        self.assertEqual(decision.arguments["amount"], 100)

    def test_selects_exchange_rate_for_a_rate_question(self) -> None:
        llm = FakeListChatModel(
            responses=[
                '{"tool": "exchange_rate", "arguments": '
                '{"base_currency": "GBP", "quote_currency": "JPY"}}'
            ]
        )
        decision = select_tool("What is the GBP to JPY rate?", llm)
        self.assertEqual(decision.tool_name, "exchange_rate")

    def test_accepts_code_fenced_json(self) -> None:
        llm = FakeListChatModel(
            responses=['```json\n{"tool": "current_weather", "arguments": {"city": "Paris"}}\n```']
        )
        decision = select_tool("Weather in Paris?", llm)
        self.assertEqual(decision.arguments["city"], "Paris")

    def test_no_tool_decision_returns_message(self) -> None:
        llm = FakeListChatModel(
            responses=['{"tool": null, "message": "I can answer weather and currency questions only."}']
        )
        decision = select_tool("Who won the 2010 World Cup?", llm)
        self.assertIsNone(decision.tool_name)
        self.assertIn("weather and currency", decision.message or "")

    def test_malformed_json_raises_assistant_error(self) -> None:
        llm = FakeListChatModel(responses=["I think this is a weather question."])
        with self.assertRaises(AssistantError):
            select_tool("Weather?", llm)

    def test_missing_tool_field_is_rejected(self) -> None:
        with self.assertRaises(AssistantError):
            parse_decision({"arguments": {"city": "Berlin"}})

    def test_non_object_arguments_are_rejected(self) -> None:
        with self.assertRaises(AssistantError):
            parse_decision({"tool": "current_weather", "arguments": "Berlin"})

    def test_empty_question_is_rejected(self) -> None:
        llm = FakeListChatModel(responses=["{}"])
        for value in ("", "   "):
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    select_tool(value, llm)


class AnswerQuestionTests(unittest.TestCase):
    def test_unknown_tool_is_reported_without_crashing(self) -> None:
        llm = FakeListChatModel(
            responses=['{"tool": "stock_price", "arguments": {"ticker": "MSFT"}}']
        )
        answer = answer_question("What is the MSFT stock price?", llm)
        self.assertTrue(answer.error)
        self.assertIn("unknown tool", answer.text.lower())

    def test_malformed_response_is_reported(self) -> None:
        llm = FakeListChatModel(responses=["not json"])
        answer = answer_question("Weather?", llm)
        self.assertTrue(answer.error)
        self.assertIn("JSON", answer.text)

    def test_executes_selected_tool_with_arguments(self) -> None:
        llm = FakeListChatModel(
            responses=['{"tool": "current_weather", "arguments": {"city": "Oslo"}}']
        )
        answer = answer_question(
            "What is the weather in Oslo?", llm, tools=[fake_weather]
        )
        self.assertFalse(answer.error)
        self.assertEqual(answer.tool_name, "current_weather")
        self.assertIn("Fake weather for Oslo", answer.text)

    def test_invalid_arguments_are_reported(self) -> None:
        llm = FakeListChatModel(
            responses=['{"tool": "strict_tool", "arguments": {"amount": "not-a-number"}}']
        )
        answer = answer_question("Use the strict tool", llm, tools=[strict_tool])
        self.assertTrue(answer.error)
        self.assertIn("invalid arguments", answer.text.lower())

    def test_no_tool_answer_is_returned_unchanged(self) -> None:
        llm = FakeListChatModel(
            responses=['{"tool": null, "message": "Only weather and currency, please."}']
        )
        answer = answer_question("Tell me a joke", llm)
        self.assertIsNone(answer.tool_name)
        self.assertEqual(answer.text, "Only weather and currency, please.")

    def test_simulated_answers_are_labelled(self) -> None:
        llm = FakeListChatModel(
            responses=['{"tool": "current_weather", "arguments": {"city": "Rome"}}']
        )
        answer = answer_question(
            "Weather in Rome?", llm, tools=[fake_weather], simulated=True
        )
        rendered = answer.render()
        self.assertTrue(rendered.startswith("[SIMULATION"))
        self.assertIn("not a live OpenAI response", rendered)


class ConfigurationTests(unittest.TestCase):
    def test_missing_key_raises_before_chatopenai_is_created(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with patch("src.assistant.load_dotenv"):
                with patch("src.assistant.ChatOpenAI") as mocked:
                    with self.assertRaises(MissingAPIKeyError):
                        create_chat_model()
                    mocked.assert_not_called()

    def test_model_comes_from_environment(self) -> None:
        environment = {"OPENAI_API_KEY": "test-placeholder-not-a-real-key", "OPENAI_MODEL": "test-model"}
        with patch.dict(os.environ, environment, clear=False):
            with patch("src.assistant.load_dotenv"):
                with patch("src.assistant.ChatOpenAI") as mocked:
                    create_chat_model()
        self.assertEqual(mocked.call_args.kwargs["model"], "test-model")

    def test_default_model_is_used_when_variable_is_absent(self) -> None:
        environment = {"OPENAI_API_KEY": "test-placeholder-not-a-real-key"}
        with patch.dict(os.environ, environment, clear=False):
            os.environ.pop("OPENAI_MODEL", None)
            with patch("src.assistant.load_dotenv"):
                with patch("src.assistant.ChatOpenAI") as mocked:
                    create_chat_model()
        self.assertEqual(mocked.call_args.kwargs["model"], DEFAULT_MODEL)


if __name__ == "__main__":
    unittest.main()
