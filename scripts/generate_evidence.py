"""Generate outputs/five_qa_evidence.md.

The LLM routing is simulated with ``FakeListChatModel`` and is labelled as such.
Weather and currency values are fetched from the two free, keyless public APIs
so the examples show real tool output. No OpenAI API call is made and no key is
read.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.language_models import FakeListChatModel  # noqa: E402

from src.assistant import answer_question  # noqa: E402

CASES = [
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


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    results = []
    for question, response in CASES:
        llm = FakeListChatModel(responses=[response])
        answer = answer_question(question, llm, simulated=True)
        results.append((question, answer))

    lines = [
        "# B9 - Five Q&A Evidence",
        "",
        "> **STATUS: LLM ROUTING SIMULATED - NOT LIVE OPENAI RESPONSES.**",
        ">",
        "> The tool-selection JSON for these five examples was produced by LangChain's "
        "`FakeListChatModel`, not by OpenAI. No OpenAI API call was made and no "
        "`OPENAI_API_KEY` was used. The weather and currency values were fetched live "
        "from the free, keyless Open-Meteo and Frankfurter APIs at the time shown below.",
        "",
        "---",
        "",
        "## Method",
        "",
        f"- **Generated:** {stamp}",
        "- **LLM routing:** `FakeListChatModel` with five canned JSON decisions (simulation).",
        "- **Weather data:** Open-Meteo geocoding + current forecast (live public API).",
        "- **Currency data:** Frankfurter v2 reference rates (live public API).",
        "- **OpenAI calls:** none.",
        "- **API keys used:** none.",
        "- **Reference-rate notice:** Frankfurter rates are reference rates, not live trading quotes.",
        "",
        "## Summary",
        "",
        "| # | Question | Tool selected | Result |",
        "|---|---|---|---:|",
    ]

    for index, (question, answer) in enumerate(results, start=1):
        status = "error" if answer.error else "ok"
        lines.append(
            f"| {index} | {question} | `{answer.tool_name or 'none'}` | {status} |"
        )

    lines.extend(["", "---", ""])

    for index, (question, answer) in enumerate(results, start=1):
        lines.extend(
            [
                f"## {index}. {question}",
                "",
                "**Mode:** Simulated LLM routing (`FakeListChatModel`)",
                "",
                f"**Question:** {question}",
                "",
                f"**Tool selected:** `{answer.tool_name or 'none'}`",
                "",
                f"**Arguments:** `{answer.arguments}`",
                "",
                "**Answer (tool output; data from live free public APIs):**",
                "",
                f"> {answer.text}",
                "",
                "---",
                "",
            ]
        )

    lines.extend(
        [
            "## What this evidence shows",
            "",
            "- The assistant routes weather questions to `current_weather`.",
            "- Amount questions route to `convert_currency`; rate-only questions route to `exchange_rate`.",
            "- The three LangChain tools execute and return readable, labelled output.",
            "- Currency answers carry the reference-rate disclaimer.",
            "",
            "## What this evidence does not show",
            "",
            "- Real OpenAI tool-selection quality, latency, or cost.",
            "- That a live `ChatOpenAI` run works: no OpenAI key or credits were used.",
            "- That the public APIs will behave identically on another date.",
            "",
            "The saved values are a snapshot. Rerun `python scripts/generate_evidence.py` "
            "to refresh them; it needs internet access for the two free APIs.",
            "",
        ]
    )

    target = ROOT / "outputs" / "five_qa_evidence.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote={target} bytes={target.stat().st_size}")
    for question, answer in results:
        print(f"tool={answer.tool_name} error={answer.error} question={question}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
