# FIP B9 - Real-Time Information Assistant

A small API-integration project that answers plain-language weather and currency
questions. LangChain tools wrap two **free, keyless public APIs**, and a LangChain
chat model selects the right tool for the question.

- **Weather:** Open-Meteo geocoding + current forecast
- **Currency:** Frankfurter v2 reference rates and conversion
- **Routing:** `ChatOpenAI` in live mode, `FakeListChatModel` in offline mode
- **No paid API credits are needed** for the weather and currency integrations

> Frankfurter rates are reference rates, not live trading quotes. Weather values
> are model estimates for a location, not local measurements.

---

## Status

| Item | Status |
|---|---|
| Open-Meteo integration | Complete, verified live on 2026-11-16 |
| Frankfurter integration | Complete, verified live on 2026-11-16 |
| LangChain tool definitions | Complete (3 tools) |
| Offline test suite | **66 passed, 0 failed, 6 live tests skipped** |
| Live public API tests | **6 passed** (run with `RUN_LIVE_TESTS=1`) |
| Offline Q&A evidence | Complete in `outputs/five_qa_evidence.md` |
| Notebook | Complete, validated, not executed |
| Live OpenAI routing | **Not tested** - no API key or credits were available |

The five Q&A examples use **simulated LLM routing** (`FakeListChatModel`) and
**live data from the free public APIs**. They are not live OpenAI responses.
No OpenAI call has been made by this project.

---

## Overview

1. The user asks a question in plain language.
2. The chat model receives a routing prompt listing three tools.
3. The model returns a small JSON decision, for example:
   `{"tool": "current_weather", "arguments": {"city": "Berlin"}}`
4. The application validates the decision and runs the selected LangChain tool.
5. The tool calls the relevant public API and returns readable text.
6. The assistant displays the tool output, including the reference-rate notice
   for currency answers.

The model chooses the tool; it never supplies weather or exchange-rate values.

```text
question
   |
   v
ChatOpenAI (live)  or  FakeListChatModel (offline)
   |
   v
validated JSON decision
   |
   +--> current_weather  --> Open-Meteo geocoding + forecast
   +--> exchange_rate    --> Frankfurter /v2/rates
   +--> convert_currency --> Frankfurter /v2/rates + local arithmetic
   |
   v
readable answer with source and disclaimer
```

---

## Features

| Feature | Implementation |
|---|---|
| City resolution | `geocode_city()` against the Open-Meteo geocoding endpoint |
| Current weather | `get_current_weather()` against the Open-Meteo forecast endpoint |
| Reference rate | `get_exchange_rate()` against Frankfurter v2 |
| Amount conversion | `convert_currency()` with local arithmetic |
| LangChain tools | `@tool` definitions with Pydantic input schemas |
| Tool selection | JSON routing prompt, validated before execution |
| Live model | `ChatOpenAI`, model from `OPENAI_MODEL` |
| Offline model | `FakeListChatModel` with canned routing JSON |
| Validation | City names, currency codes, amounts, tool names, arguments |
| Error handling | Unknown city, unsupported currency, timeout, HTTP error, bad JSON |
| CLI modes | Live question, interactive, offline demo, public API checks |
| Tests | 66 offline + 6 live public API checks |
| Evidence | Five labelled simulated-routing Q&A examples |

---

## Project structure

```text
B9/
|-- .env.example
|-- .gitignore
|-- README.md
|-- app.py                          CLI entry point
|-- requirements.txt
|-- docs/
|   `-- risks_and_limitations.md
|-- notebooks/
|   `-- B9_Real_Time_Information_Assistant.ipynb
|-- outputs/
|   `-- five_qa_evidence.md
|-- scripts/
|   `-- generate_evidence.py
|-- src/
|   |-- __init__.py
|   |-- assistant.py                routing, answer assembly, settings
|   |-- currency_api.py             Frankfurter client
|   |-- errors.py                   project exceptions
|   |-- http_client.py              JSON-over-HTTPS helper
|   |-- tools.py                    LangChain tool definitions
|   `-- weather_api.py              Open-Meteo client
|-- tests/
|   |-- test_assistant.py
|   |-- test_currency.py
|   |-- test_http_client.py
|   |-- test_live_apis.py           skipped unless RUN_LIVE_TESTS=1
|   |-- test_tools.py
|   `-- test_weather.py
`-- .venv/                          local virtual environment (not published)
```

`.venv/` and `.env` are ignored by `.gitignore`.

---

## Requirements

- Windows PowerShell (commands below); any OS with Python works
- Python **3.13.17** was used; Python 3.11+ should work
- Internet access for live public API data
- An OpenAI API key **only** for live model routing
- No key or credits for the weather and currency APIs

`requirements.txt` lists unpinned package names:

```text
langchain
langchain-openai
python-dotenv
notebook
ipykernel
```

Versions installed for this build:

| Package | Version |
|---|---:|
| `langchain` | 1.5.0 |
| `langchain-openai` | 1.8.0 |
| `langchain-core` | 1.8.1 |
| `openai` | 3.51.0 |
| `python-dotenv` | 1.2.4 |
| `notebook` | 7.6.5 |
| `ipykernel` | 7.4.0 |

Pin versions if you need a fully reproducible environment.

---

## Installation

Open PowerShell in the cloned `B9` project folder, or change into it with `cd`:

```powershell
cd path\to\B9
```

Create and use a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe --version
```

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No project package needs to be installed: the code runs from the project root
with `src` as a local package.

---

## Configuration

Live model routing needs an OpenAI key. The public API checks and offline demo do
not.

1. Copy the template:

   ```powershell
   copy .env.example .env
   ```

2. Edit `.env`:

   ```text
   OPENAI_API_KEY=your_api_key_here
   OPENAI_MODEL=gpt-4o-mini
   ```

   Replace `your_api_key_here` with your own key. Never commit `.env`.

3. `OPENAI_MODEL` is optional. If it is absent or empty, the code uses
   `DEFAULT_MODEL = "gpt-4o-mini"`. If you copied `.env.example` unchanged, you
   must replace `your_model_name_here` or delete the line; an invalid model name
   produces an OpenAI `BadRequestError`.

`.env` is loaded with `load_dotenv(override=False)`, so real environment
variables take precedence over the file.

Security rules:

- Never print, log, or store the key.
- Never put a key in source code, tests, the notebook, or the README.
- Revoke the key immediately if it is exposed.
- A ChatGPT subscription does not automatically include API credits.

---

## Running the assistant

### One live question

```powershell
.\.venv\Scripts\python.exe app.py "What is the weather in Berlin?"
```

This needs `OPENAI_API_KEY`. The model chooses the tool; the tool calls the
public API.

### Interactive live mode

```powershell
.\.venv\Scripts\python.exe app.py
```

Type `quit` or `exit` to stop.

### Offline routing demo

```powershell
.\.venv\Scripts\python.exe app.py --offline
```

This runs five example questions. Routing is produced by `FakeListChatModel`
(simulated), while weather and currency data come from the live free APIs.
Every answer is prefixed with a simulation banner. No OpenAI key is used.

### Live public API checks

```powershell
.\.venv\Scripts\python.exe app.py --check-apis
```

This checks geocoding, current weather, a reference rate, and a conversion. It
needs no OpenAI key.

### Notebook

```powershell
.\.venv\Scripts\python.exe -m notebook notebooks\B9_Real_Time_Information_Assistant.ipynb
```

The notebook is an educational walkthrough. It was validated but not executed;
its live cells need internet access and, for OpenAI routing, a configured key.

---

## Tests

### Offline suite

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected result:

```text
Ran 72 tests in ...s

OK (skipped=6)
```

The six skipped tests are the live public API checks. The other 66 tests make
no network calls and no OpenAI calls.

Coverage:

- HTTP helper: valid JSON, HTTP errors, timeouts, connection errors, bad JSON;
- weather: geocoding, unknown city, missing fields, invalid coordinates;
- currency: code normalisation, amount validation, rate parsing, 422 mapping,
  same-currency shortcuts, conversion arithmetic;
- tools: registration, schemas, readable output, friendly errors;
- assistant: weather/rate/conversion routing, code-fenced JSON, malformed JSON,
  unknown tools, invalid arguments, simulation labelling, missing-key handling.

### Live public API suite

```powershell
$env:RUN_LIVE_TESTS="1"
.\.venv\Scripts\python.exe -m unittest tests.test_live_apis -v
```

Result on 2026-11-16: **6 tests passed** against Open-Meteo and Frankfurter.
These tests need no OpenAI key. If the network or a service is unavailable,
they fail honestly; they do not silently pass.

---

## Five Q&A evidence

`outputs/five_qa_evidence.md` contains five questions covering both APIs:

1. Weather in Berlin
2. Weather in Tokyo
3. 100 USD to EUR
4. GBP to JPY rate
5. 250 EUR to INR

The file is clearly marked:

> **STATUS: LLM ROUTING SIMULATED - NOT LIVE OPENAI RESPONSES.**

The routing JSON was supplied by `FakeListChatModel`. Weather and currency values
were fetched from the live free public APIs when the file was generated. The
evidence does not demonstrate OpenAI model quality or a successful OpenAI call.

Regenerate it with:

```powershell
.\.venv\Scripts\python.exe scripts\generate_evidence.py
```

This needs internet access for the two public APIs and no OpenAI key.

---

## Public APIs

### Open-Meteo

- Geocoding: `https://geocoding-api.open-meteo.com/v1/search`
- Forecast: `https://api.open-meteo.com/v1/forecast`
- Free and keyless; check Open-Meteo's current terms for attribution and usage limits
- Unknown cities return a 200 response without a `results` key, which the client
  maps to `LocationNotFoundError`
- Current conditions use `current=temperature_2m,relative_humidity_2m,
  apparent_temperature,weather_code,wind_speed_10m`

### Frankfurter v2

- Rates: `https://api.frankfurter.dev/v2/rates?base=USD&quotes=EUR`
- Response: a JSON array of `{date, base, quote, rate}` objects
- Invalid currency codes return HTTP 422 with a JSON `message`
- Free, keyless, sourced from European Central Bank reference rates
- **Reference rates only: not live trading quotes**

---

## Security and limitations

- No API key is stored in the repository; `.env.example` has placeholders only.
- `.env`, `.venv`, `__pycache__`, `*.pyc`, notebooks checkpoints, and generated
  files are ignored by `.gitignore`.
- Live questions are sent to OpenAI; city names go to Open-Meteo; currency pairs
  go to Frankfurter. Amounts are processed locally.
- Weather values are model estimates; city geocoding can pick the wrong place.
- Currency rates are reference rates, not trading quotes.
- The model can choose the wrong tool; the code validates the decision but does
  not measure whether it was the best choice.
- History is not kept, responses are not cached, and there is no production
  hardening, monitoring, or rate limiting.
- Offline tests do not prove live OpenAI behaviour.
- Requirements are unpinned.

See [`docs/risks_and_limitations.md`](docs/risks_and_limitations.md) for the full
discussion.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `MissingAPIKeyError` | `OPENAI_API_KEY` unset or blank | Create `.env` or set the variable |
| `AuthenticationError` | Key invalid, revoked, or inactive | Check the key in the OpenAI dashboard |
| `BadRequestError` | Invalid `OPENAI_MODEL` (often the placeholder) | Set a valid model or delete the line |
| `RateLimitError` | OpenAI quota or rate limit reached | Check billing and retry later |
| `LocationNotFoundError` / "No location found" | City not in the geocoding database | Try a nearby larger city or add a country |
| `UnsupportedCurrencyError` | Code not supported by Frankfurter | Use a supported three-letter code |
| `APITimeoutError` / `APIConnectionError` | Network problem | Check the connection and retry |
| `APIResponseError` | Unexpected upstream payload | Retry; the API may have changed |
| `ModuleNotFoundError` | Dependencies missing | Install `requirements.txt` into `.venv` |

---

## Documentation

- [`docs/risks_and_limitations.md`](docs/risks_and_limitations.md)
- [`outputs/five_qa_evidence.md`](outputs/five_qa_evidence.md)
- [`notebooks/B9_Real_Time_Information_Assistant.ipynb`](notebooks/B9_Real_Time_Information_Assistant.ipynb)
- [`src/assistant.py`](src/assistant.py)
- [`src/tools.py`](src/tools.py)
- [`src/weather_api.py`](src/weather_api.py)
- [`src/currency_api.py`](src/currency_api.py)
- [`tests/test_live_apis.py`](tests/test_live_apis.py)
