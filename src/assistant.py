"""LangChain assistant that routes plain-language questions to tools.

The routing step asks the chat model for a JSON decision::

    {"tool": "current_weather", "arguments": {"city": "Berlin"}}

or::

    {"tool": null, "message": "I can only answer weather and currency questions."}

The same function works with a live ``ChatOpenAI`` model and with LangChain's
``FakeListChatModel`` for offline tests, because both are chat models that
accept a list of messages. No tool is ever chosen by keyword matching in this
module: the model makes the decision, and the decision is validated before a
tool runs.

OpenAI is used only to choose the tool and its arguments. Weather and currency
data comes from the free, keyless Open-Meteo and Frankfurter APIs.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from .errors import AssistantError, InputValidationError, MissingAPIKeyError
from .tools import ALL_TOOLS

DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2

ROUTER_SYSTEM_PROMPT = """You are the routing component of a real-time information assistant.
You do not answer weather or currency questions from memory. You choose exactly
one tool and supply its arguments, then the application runs the tool and shows
the result.

Available tools:

1. current_weather
   arguments: {"city": "Berlin"}
   Use for present weather, temperature, conditions, humidity or wind in a city.

2. exchange_rate
   arguments: {"base_currency": "USD", "quote_currency": "EUR"}
   Use when the user asks for a rate between two currencies without an amount.

3. convert_currency
   arguments: {"amount": 100, "from_currency": "USD", "to_currency": "EUR"}
   Use when the user asks to convert a specific amount. The amount must be a
   positive number.

Rules:
- Reply with a single JSON object and nothing else. No markdown fences, no prose.
- Use exactly one of the tool names above, or null when no tool fits.
- Currency codes must be three letters, such as USD, EUR, GBP or JPY.
- Never invent weather data or exchange rates.
- If the question is outside weather and currency, use:
  {"tool": null, "message": "I can answer weather and currency questions only."}

Examples:
Question: What is the weather in Berlin?
{"tool": "current_weather", "arguments": {"city": "Berlin"}}

Question: How much is 100 USD in EUR?
{"tool": "convert_currency", "arguments": {"amount": 100, "from_currency": "USD", "to_currency": "EUR"}}

Question: What is the GBP to JPY rate?
{"tool": "exchange_rate", "arguments": {"base_currency": "GBP", "quote_currency": "JPY"}}
"""

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


@dataclass(frozen=True)
class Settings:
    """Non-secret runtime settings."""

    model: str
    api_key_configured: bool


@dataclass(frozen=True)
class ToolDecision:
    """A validated routing decision returned by the language model."""

    tool_name: str | None
    arguments: dict[str, Any] = field(default_factory=dict)
    message: str | None = None


@dataclass(frozen=True)
class AssistantAnswer:
    """The final text plus provenance for the answer."""

    text: str
    tool_name: str | None
    arguments: dict[str, Any]
    simulated: bool = False
    error: bool = False

    def render(self) -> str:
        if self.simulated:
            banner = "[SIMULATION - FakeListChatModel routing, not a live OpenAI response]"
            return f"{banner}\n{self.text}"
        if self.error:
            return f"Assistant error: {self.text}"
        return self.text


def get_settings() -> Settings:
    """Read non-secret settings from the environment."""

    load_dotenv(override=False)
    return Settings(
        model=os.getenv("OPENAI_MODEL") or DEFAULT_MODEL,
        api_key_configured=bool(os.getenv("OPENAI_API_KEY", "").strip()),
    )


def create_chat_model() -> ChatOpenAI:
    """Create the live OpenAI chat model, failing fast without a key."""

    load_dotenv(override=False)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise MissingAPIKeyError(
            "No OpenAI API key found. Set OPENAI_API_KEY in your environment or in a "
            "local .env file. The offline demo and the public API checks do not need a key."
        )
    model = os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=0,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )


def build_router_prompt() -> ChatPromptTemplate:
    """Build the routing prompt without templating the JSON examples."""

    return ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
    )


def _message_text(message: BaseMessage | Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return str(content)


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = _CODE_FENCE.sub("", text.strip()).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AssistantError("The language model did not return a JSON object.")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AssistantError("The language model returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise AssistantError("The language model returned JSON that is not an object.")
    return payload


def parse_decision(payload: dict[str, Any]) -> ToolDecision:
    """Validate the routing JSON before any tool is executed."""

    if "tool" not in payload:
        raise AssistantError("The routing JSON is missing the 'tool' field.")

    tool_name = payload["tool"]
    if tool_name is None:
        message = payload.get("message")
        return ToolDecision(
            tool_name=None,
            arguments={},
            message=message if isinstance(message, str) and message.strip() else None,
        )

    if not isinstance(tool_name, str) or not tool_name.strip():
        raise AssistantError("The routing JSON contains an invalid tool name.")

    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        raise AssistantError("The routing JSON 'arguments' field must be an object.")

    return ToolDecision(tool_name=tool_name.strip(), arguments=arguments)


def select_tool(question: str, llm: BaseChatModel) -> ToolDecision:
    """Ask a chat model which tool to use for a question."""

    if not isinstance(question, str):
        raise InputValidationError("Question must be provided as text.")
    cleaned = question.strip()
    if not cleaned:
        raise InputValidationError("Question cannot be empty.")

    messages = build_router_prompt().format_messages(question=cleaned)
    response = llm.invoke(messages)
    return parse_decision(_extract_json(_message_text(response)))


def answer_question(
    question: str,
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
    simulated: bool = False,
) -> AssistantAnswer:
    """Route a question, run the selected tool, and return its result."""

    available = tools if tools is not None else ALL_TOOLS
    tool_map = {item.name: item for item in available}

    try:
        decision = select_tool(question, llm)
    except AssistantError as exc:
        return AssistantAnswer(
            text=str(exc),
            tool_name=None,
            arguments={},
            simulated=simulated,
            error=True,
        )

    if decision.tool_name is None:
        return AssistantAnswer(
            text=decision.message or "No suitable tool was selected for this question.",
            tool_name=None,
            arguments={},
            simulated=simulated,
        )

    selected = tool_map.get(decision.tool_name)
    if selected is None:
        return AssistantAnswer(
            text=f"The model selected an unknown tool: {decision.tool_name}.",
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            simulated=simulated,
            error=True,
        )

    try:
        output = selected.invoke(decision.arguments)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        detail = first.get("msg", "invalid arguments")
        return AssistantAnswer(
            text=f"The model supplied invalid arguments for {decision.tool_name}: {detail}.",
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            simulated=simulated,
            error=True,
        )
    except AssistantError as exc:
        return AssistantAnswer(
            text=str(exc),
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            simulated=simulated,
            error=True,
        )

    return AssistantAnswer(
        text=str(output),
        tool_name=decision.tool_name,
        arguments=decision.arguments,
        simulated=simulated,
    )
