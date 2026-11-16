# B9 Risks and Limitations

This document records the practical risks of the Real-Time Information
Assistant and the limits of what the project verifies. It is an educational
prototype, not a production or financial service.

---

## 1. Third-party public API dependency

The assistant depends on three external services:

| Service | Used for | Key required | Cost |
|---|---|---|---|
| Open-Meteo geocoding | City name to coordinates | No | Free |
| Open-Meteo forecast | Current weather | No | Free |
| Frankfurter v2 | Reference exchange rates | No | Free |
| OpenAI API | Tool selection only | Yes | Paid |

Risks:

- Any service can be slow, unavailable, rate-limited, or changed without notice.
- Free services usually publish fair-use expectations but no uptime guarantee.
- Endpoint paths, response fields, or error formats may change.
- Open-Meteo and Frankfurter may limit heavy or automated use.
- The project does not cache responses, retry public API calls, or fall back to a
  second provider.

If a public API fails, the affected tool returns a short error message and the
other tools remain usable. The assistant never invents data to cover a failure.

---

## 2. Reference rates are not trading quotes

Frankfurter publishes **reference exchange rates** sourced from the European
Central Bank. They are informational only.

- They are **not live trading quotes** and are not suitable for trading,
  settlement, invoicing, accounting, or arbitrage.
- Rates are typically updated on working days and may lag the market.
- A rate returned for one date may differ from the rate on another date.
- Frankfurter v2 also exposes some non-fiat assets; only three-letter codes are
  accepted by this project, and support depends on the service.
- The project does not add spreads, fees, or taxes. A real conversion would.

Every currency answer includes the disclaimer. Do not remove it.

---

## 3. Weather accuracy and geocoding ambiguity

- Open-Meteo model data is an estimate for a grid cell, not a measurement at the
  user's exact street address.
- City names can be ambiguous: the geocoder returns the best match for the name,
  which may be the wrong country or region.
- The project requests only the first geocoding result and does not let the user
  choose among candidates.
- Weather conditions can change quickly; the observation time is included in
  every answer and should be checked.
- The weather code mapping covers standard WMO codes. Unknown codes are shown as
  "Unknown weather code" rather than guessed.

---

## 4. Language-model risks

OpenAI is used **only to choose a tool and its arguments**, not to produce
weather or currency data.

Risks:

- The model may choose the wrong tool, for example `exchange_rate` instead of
  `convert_currency`, or miss the intent entirely.
- It may return malformed JSON, an unknown tool name, or invalid arguments.
- It may answer a question from general knowledge instead of requesting a tool.
- Model behaviour, latency, and price can change between versions.
- A prompt-injection attempt inside a user question could try to redirect the
  model. The application validates the tool name and arguments before execution,
  which limits the damage but does not make the model trustworthy.

The code validates the routing JSON, checks that the tool exists, and lets the
tool input schema reject bad arguments. It does not evaluate whether the chosen
tool was the best choice for the question.

---

## 5. Cost and OpenAI usage

- The free public APIs need no payment, but OpenAI usage is billed separately.
- A ChatGPT subscription does **not** automatically include API credits.
- Each live question sends one routing request to OpenAI. Token usage depends on
  the question and the router prompt.
- No streaming, batching, caching, or spend cap is implemented in the project.
- Use the OpenAI dashboard to set budgets and monitor usage.
- The offline demo and `--check-apis` make **no OpenAI calls** and cost nothing.

---

## 6. API key security

- The key is read from `OPENAI_API_KEY` or a local `.env` file.
- `.env` is ignored by `.gitignore` and must never be committed.
- `.env.example` contains placeholders only.
- The code reports only whether a key is configured, never its value.
- No key, header, or raw response body is printed or written to evidence files.
- The key is a billing credential. Revoke and replace it immediately if exposed.
- Deleting a key from a file does not remove it from shell history, editor backups,
  or version-control history.

---

## 7. Privacy and data transmission

A live question is transmitted to OpenAI so the model can select a tool. The
question may contain a city name, currency codes, an amount, or other text the
user typed. Do not include personal, confidential, or sensitive information.

Separately:

- The city name is sent to Open-Meteo's geocoding service.
- Coordinates are sent to Open-Meteo's forecast service.
- Currency codes are sent to Frankfurter.
- Amounts are processed locally and are **not** sent to Frankfurter (only the
  currency pair is sent).

Terminal output, notebook outputs, screenshots, and saved transcripts may retain
questions and answers. Clear them before sharing. The five Q&A evidence file
contains only public-API data and simulated routing, not private user data.

---

## 8. Internet dependency and timeouts

- Live weather and currency data require internet access.
- Timeouts default to 10 seconds for public APIs and 30 seconds for OpenAI.
- On timeout, connection failure, HTTP error, or malformed JSON, the client raises
  a project exception and the tool returns a short failure message.
- There is no offline cache of live data. The notebook and tests use mocked
  responses for offline verification.

---

## 9. Missing key and authentication errors

`MissingAPIKeyError` is raised by `create_chat_model()` before `ChatOpenAI` is
constructed when `OPENAI_API_KEY` is missing or blank.

`AuthenticationError` is different: it is returned by the OpenAI API after a
request is sent with a key that the service rejects. It can mean the key is
invalid, revoked, inactive, or not permitted to use the selected model.

Never "fix" a missing key by putting a key in source code, tests, notebooks, or
the README. Create `.env` locally and restart the program.

---

## 10. Limits of offline testing

The offline suite uses mocked HTTP responses and `FakeListChatModel`. It verifies:

- validation of city names, currency codes, and amounts;
- parsing of representative API payloads;
- mapping of timeouts, HTTP errors, and malformed JSON to friendly errors;
- tool registration and readable tool output;
- routing decisions for weather, rate, and conversion questions;
- rejection of malformed routing JSON, unknown tools, and invalid arguments;
- missing-key behaviour before a client is created.

It does **not** verify:

- real public API availability, latency, quotas, or payload changes;
- real OpenAI tool-selection quality, authentication, billing, or latency;
- behaviour under concurrent use, retries, or production load;
- factual correctness of any weather forecast or exchange rate.

Passing offline tests means the local logic behaves as designed. It does not
prove that live services will succeed.

---

## 11. Other limitations

- No caching, persistence, conversation history, or user accounts.
- No rate limiting, monitoring, audit logging, or deployment hardening.
- No currency conversion fees, spreads, or tax handling.
- No country/region selection for ambiguous city names.
- Requirements are unpinned, so future installs may resolve different versions.
- The default OpenAI model may not be available to every account; set
  `OPENAI_MODEL` explicitly.

---

## 12. Mitigation checklist

Before live use:

- [ ] `.env` exists locally and is not committed or screenshotted.
- [ ] `OPENAI_MODEL` is a valid model for the account, not a placeholder.
- [ ] API budgets and usage alerts are configured.
- [ ] Questions contain no personal or confidential data.
- [ ] Currency answers are labelled as reference rates, not trading quotes.
- [ ] Weather answers are checked against the observation time.
- [ ] Notebook outputs and terminal transcripts are cleared before sharing.
- [ ] Simulated routing is never described as live OpenAI output.
