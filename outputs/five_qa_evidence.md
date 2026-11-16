# B9 - Five Q&A Evidence

> **STATUS: LLM ROUTING SIMULATED - NOT LIVE OPENAI RESPONSES.**
>
> The tool-selection JSON for these five examples was produced by LangChain's `FakeListChatModel`, not by OpenAI. No OpenAI API call was made and no `OPENAI_API_KEY` was used. The weather and currency values were fetched live from the free, keyless Open-Meteo and Frankfurter APIs at the time shown below.

---

## Method

- **Generated:** 2026-11-16 20:43 UTC
- **LLM routing:** `FakeListChatModel` with five canned JSON decisions (simulation).
- **Weather data:** Open-Meteo geocoding + current forecast (live public API).
- **Currency data:** Frankfurter v2 reference rates (live public API).
- **OpenAI calls:** none.
- **API keys used:** none.
- **Reference-rate notice:** Frankfurter rates are reference rates, not live trading quotes.

## Summary

| # | Question | Tool selected | Result |
|---|---|---|---:|
| 1 | What is the weather in Berlin right now? | `current_weather` | ok |
| 2 | Do I need an umbrella in Tokyo? What is the weather there? | `current_weather` | ok |
| 3 | How much is 100 USD in EUR? | `convert_currency` | ok |
| 4 | What is the exchange rate from GBP to JPY? | `exchange_rate` | ok |
| 5 | Convert 250 EUR to INR. | `convert_currency` | ok |

---

## 1. What is the weather in Berlin right now?

**Mode:** Simulated LLM routing (`FakeListChatModel`)

**Question:** What is the weather in Berlin right now?

**Tool selected:** `current_weather`

**Arguments:** `{'city': 'Berlin'}`

**Answer (tool output; data from live free public APIs):**

> Berlin, State of Berlin, Germany: 8.4 C (feels like 4.6 C), overcast; humidity 75%; wind 16.5 km/h; observed 2026-11-16T21:30 (Europe/Berlin).

---

## 2. Do I need an umbrella in Tokyo? What is the weather there?

**Mode:** Simulated LLM routing (`FakeListChatModel`)

**Question:** Do I need an umbrella in Tokyo? What is the weather there?

**Tool selected:** `current_weather`

**Arguments:** `{'city': 'Tokyo'}`

**Answer (tool output; data from live free public APIs):**

> Tokyo, Japan: 10.6 C (feels like 9.1 C), partly cloudy; humidity 76%; wind 3.7 km/h; observed 2026-11-17T05:30 (Asia/Tokyo).

---

## 3. How much is 100 USD in EUR?

**Mode:** Simulated LLM routing (`FakeListChatModel`)

**Question:** How much is 100 USD in EUR?

**Tool selected:** `convert_currency`

**Arguments:** `{'amount': 100, 'from_currency': 'USD', 'to_currency': 'EUR'}`

**Answer (tool output; data from live free public APIs):**

> 100.00 USD = 90.57 EUR at the reference rate 0.90573 (2026-11-16). Frankfurter rates are reference rates published by the European Central Bank; they are not live trading quotes.

---

## 4. What is the exchange rate from GBP to JPY?

**Mode:** Simulated LLM routing (`FakeListChatModel`)

**Question:** What is the exchange rate from GBP to JPY?

**Tool selected:** `exchange_rate`

**Arguments:** `{'base_currency': 'GBP', 'quote_currency': 'JPY'}`

**Answer (tool output; data from live free public APIs):**

> 1 GBP = 211.4 JPY (reference rate, 2026-11-16). Frankfurter rates are reference rates published by the European Central Bank; they are not live trading quotes.

---

## 5. Convert 250 EUR to INR.

**Mode:** Simulated LLM routing (`FakeListChatModel`)

**Question:** Convert 250 EUR to INR.

**Tool selected:** `convert_currency`

**Arguments:** `{'amount': 250, 'from_currency': 'EUR', 'to_currency': 'INR'}`

**Answer (tool output; data from live free public APIs):**

> 250.00 EUR = 25,960.00 INR at the reference rate 103.84 (2026-11-16). Frankfurter rates are reference rates published by the European Central Bank; they are not live trading quotes.

---

## What this evidence shows

- The assistant routes weather questions to `current_weather`.
- Amount questions route to `convert_currency`; rate-only questions route to `exchange_rate`.
- The three LangChain tools execute and return readable, labelled output.
- Currency answers carry the reference-rate disclaimer.

## What this evidence does not show

- Real OpenAI tool-selection quality, latency, or cost.
- That a live `ChatOpenAI` run works: no OpenAI key or credits were used.
- That the public APIs will behave identically on another date.

The saved values are a snapshot. Rerun `python scripts/generate_evidence.py` to refresh them; it needs internet access for the two free APIs.
