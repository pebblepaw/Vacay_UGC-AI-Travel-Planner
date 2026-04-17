# Codex Report

Test date: April 17, 2026.

## Checklist

- [x] Pull and test the browser-booking PR
- [x] Make the booking path run on Gemini and DashScope/Qwen
- [x] Migrate video analysis to `google.genai`
- [x] Split model choice by role with config
- [x] Fix video import so it fails honestly on analyzer errors
- [x] Fix map location resolution so new imports pin real locations
- [ ] Make meal searches use the itinerary around the noon slot
- [ ] Make chat reply language configurable
- [ ] Parse real booking requests from normal English follow-ups
- [ ] Make the chat input expand as the user types

I pulled the latest `main`, including the booking/browser PR, then tested the flow locally on port `8010` for the backend and `3000` for the frontend.

I used `Sample_Inputs/TikTok-Links.md`, specifically the Roady TikTok URL. The trip import completed, but the local video-analysis key in `.env` was rejected by Gemini, so that sample produced an empty trip. I still used that trip for the booking E2E, because the flight flow does not depend on POIs being present.

## Bottom line

This browser feature is a good proof of concept. It is not yet a general booking agent.

What worked in my live test:

- The chat agent understood a natural-language flight request.
- It fetched 8 real Trip.com flight options.
- The UI showed those options and let me choose one.
- The backend Playwright checkout runner reached Trip.com's passenger/contact page in its own automated browser session.
- The frontend then opened a Trip.com continuation tab for the user.

What did not fully hold up:

- The user-facing tab did not open directly on the passenger form in my test. It opened on Trip.com's sign-in page, with a `backUrl` to the passenger page.
- That means the backend automation session and the user's browser session are not the same session.
- So the claim "it brings the user to the booking page" is only partly true. The automation reached that page. The user saw a login gate first.

The evidence is clear:

- Backend automation reached the passenger page:
  - `backend/data/booking_artifacts/checkout_pre_payment_20260417_045945.png`
- User-facing Trip.com tab opened on sign-in:
  - `.playwright-cli/page-2026-04-16T21-01-02-973Z.png`
- Main app after selection:
  - `.playwright-cli/page-2026-04-16T21-00-34-022Z.png`

## What It Can Do

Right now, the real, verified path is:

1. Accept a flight request in chat.
2. Search Trip.com for flights.
3. Show live flight options in the chat UI.
4. Accept a user selection.
5. Drive a backend Playwright browser into the Trip.com checkout flow.
6. Stop before payment.

That is real.

## What It Cannot Do

It is not a general-purpose commerce agent yet.

- It is not proven on Expedia, Booking.com, Agoda, airline sites, or arbitrary ticket sites.
- It is not proven for zoo tickets, museum tickets, tours, or timed-entry attractions.
- The tool schema mentions `train`, `hotel`, and `attraction`, but the real automation is still heavily Trip.com-flight-specific.
- It does not preserve the live browser session from backend automation into the user's browser.
- It does not complete payment. That guardrail is correct and should stay.

So the short answer is:

- Can it book from websites other than Trip.com? Not reliably. The code shape gestures at that, but the verified implementation is still Trip.com-centric.
- Can it book zoo tickets? Not as a trustworthy feature today.

## What I Changed

- Refactored agent LLM selection so the PR-added browser path now works with either DashScope/Qwen or Gemini.
- Added `auto` provider fallback so the system can choose the available provider instead of failing early.
- Normalized legacy Gemini model names so old `gemini-2.0-flash` configs now resolve to `gemini-2.5-flash`.
- Wired `browser_use_worker` to the shared LLM resolver instead of hard-coding DashScope assumptions.
- Fixed English route parsing so `"to Shanghai Pudong on 2026-05-10"` no longer becomes `"Shanghai Pudong On"`.
- Fixed a frontend chat bug where rapid message creation reused `Date.now()` IDs, which caused duplicate React keys and a broken post-selection UI state.
- Updated the booking handoff message so it now warns that Trip.com may ask the user to sign in before returning to the traveler page.
- Added focused backend and frontend tests for the provider resolver, Gemini compatibility, route parsing, and client message IDs.

## How Good The Browser Feature Is

My assessment: useful demo, not production-ready booking.

Strengths:

- The search stage is real.
- The option picker is usable.
- The checkout runner can navigate Trip.com far enough to prove the selectors and flow are not fake.
- The code now runs on both Gemini and DashScope/Qwen for the booking agent path.

Weak points:

- Session handoff is the main flaw. The backend reaches the traveler page, but the user's browser gets a fresh Trip.com session.
- The system uses a mix of generic names and Trip.com-specific code. That makes the feature look broader than it is.
- Booking context is cached in memory in `backend/routers/chat.py`, so it is fragile across restarts and does not scale cleanly.
- The sample-input ingest path still depends on deprecated Gemini code and a valid Gemini key.

## Proposed Improvements

I would not rewrite the whole project. I would fix the browser/session boundary, move booking state into durable graph state, then split model choice and provider support into clear layers.

### 1. Keep one real browser session from search to handoff

The code does not sign in to Trip.com today. It does not need auth to get prices. It opens public Trip.com search URLs and scrapes the results page.

`backend/services/automation/browser_use_worker.py`

```python
return [
    "https://www.trip.com/flights/showfarefirst/?..."
]
```

The checkout step also starts a fresh anonymous browser. It does not load cookies, a saved profile, or a storage-state file.

`backend/services/automation/playwright_checkout.py`

```python
browser = await p.chromium.launch(headless=headless)
page = await browser.new_page()
await page.goto(deeplink, wait_until="domcontentloaded", timeout=45000)
```

The frontend then opens only the URL. It does not get the backend browser's cookies.

`frontend/src/contexts/TripContext.tsx`

```ts
window.open(msg.content, '_blank', 'noopener,noreferrer');
```

That is why prices work but handoff breaks. Search is public. Session reuse is not.

The backend artifact proves the anonymous automation browser reached the Trip.com passenger page. The user-facing tab proves the frontend opened a fresh Trip.com session and got sent to sign-in first.

What to do:

- Add a `BookingBrowserSessionManager`. Give each booking thread one browser profile directory, such as `backend/data/browser_profiles/{thread_id}`.
- Replace `chromium.launch()` plus `browser.new_page()` with `chromium.launch_persistent_context(profile_dir, headless=False)` in the booking flow. Playwright documents this as the way to keep cookies and local storage in one user data directory. Sources:
  - [Playwright Python: `launch_persistent_context`](https://playwright.dev/python/docs/api/class-browsertype)
  - [Playwright authentication state](https://playwright.dev/docs/auth)
- Reuse the same persistent context in both the search step and the checkout step. Right now search and checkout are two unrelated browser sessions.
- Store the booking `thread_id` or `session_id` in graph state, not just the selected offer.
- For local use, stop opening a plain URL after checkout. Leave the real headed Playwright window open and tell the user to continue there. That is the same session. A plain URL is not.

Watch out:

- A persistent profile only helps if the same browser context survives from search to user handoff.
- If the app ever runs remotely, a plain browser tab on the user's machine still will not share the server browser's cookies. Then you need a streamable browser session, not `window.open`.
- One profile directory cannot be opened by two Chromium instances at once.

### 2. Put booking state in LangGraph, not module memory

The booking cache is a Python dictionary that lives inside one FastAPI process.

`backend/routers/chat.py`

```python
_BOOKING_SESSION: dict[str, dict] = {}
cached = _BOOKING_SESSION.get(trip_id) or {}
...
_BOOKING_SESSION[trip_id] = {
    "booking_context": result.get("booking_context"),
    "booking_offers": result.get("booking_offers"),
    "selected_offer": result.get("selected_offer"),
    "booking_result": result.get("booking_result"),
}
```

That is the shortcut. LangGraph already has `booking_context`, `booking_offers`, `selected_offer`, and `booking_result` in `AgentState`, but the app does not persist graph state between requests. It rebuilds state from `_BOOKING_SESSION` by hand.

The graph is also compiled without a checkpointer, and each request is invoked without a `thread_id`.

`backend/agent/graph.py`

```python
app = workflow.compile(interrupt_before=["human_review"])
```

`backend/routers/chat.py`

```python
result = await app.ainvoke(
    initial_state,
    config={"recursion_limit": 50},
)
```

The shortfall is simple:

- Restart the backend and the booking context is gone.
- Run two backend workers and each worker gets its own cache.
- Open the same trip in two tabs and both tabs can overwrite the same in-memory booking state.
- You cannot resume a paused graph cleanly after a crash or deploy.

LangGraph persistence fixes the root problem. Its checkpointer saves graph state after each step and uses `thread_id` to resume the same thread later. Its interrupt system can pause and continue a run without rebuilding context by hand. Sources:

- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

What to do:

- Compile the graph with a real checkpointer.
- Pass a stable `thread_id` on every chat call. Use a user-and-trip key, not just `trip_id`, if multiple users will ever share trips.
- Remove `_BOOKING_SESSION` from `backend/routers/chat.py`.
- Let LangGraph load and save `booking_context`, `booking_offers`, `selected_offer`, and `booking_result` as part of `AgentState`.
- If you want a true pause/resume booking flow, use `interrupt()` for the "pick an offer" and "continue checkout" steps, then resume the same thread instead of sending magic follow-up text like `option_id: offer_1`.

Watch out:

- The current graph already uses `interrupt_before=["human_review"]`, but without a persistent checkpointer and a stable thread ID it is not a durable workflow.
- If you stay with plain chat messages instead of `Command(resume=...)`, the checkpointer still helps. You just lose some of LangGraph's cleaner resume semantics.

### 3. Migrate off `google.generativeai`

This codebase still uses the deprecated Gemini Python SDK for video analysis.

- Google now recommends the unified `google.genai` client.
- This is not cosmetic. The older package is already warning at runtime.

Source:

- [Google GenAI migration guide](https://ai.google.dev/gemini-api/docs/migrate)

What to do:

- Move `backend/services/gemini_analyzer.py` to `google.genai`.
- Keep the model name behind the same normalization layer used by `backend/llm.py`.
- Add one regression test that mocks the new client and proves the analyzer respects the configured Gemini model.

### 4. Split model choice by role, not just by provider

The agent nodes do not choose models independently today. They all call the same helper.

`backend/agent/nodes/orchestrator.py`

```python
llm = get_agent_llm(temperature=0)
```

The same call appears in `orchestrator.py`, `travel_editor.py`, `search_agent.py`, `booking_agent.py`, `critic.py`, and `chitchat.py`. So right now the orchestrator cannot be stronger while the subagents stay cheaper. They all share the same provider and the same model.

There is a second problem. Some non-graph paths still choose models outside that shared helper. The video analyzer is still Gemini-specific.

That is what I meant by "agents choose models in their own way." Most graph nodes share one global choice. Some side paths bypass that choice.

What to do:

- Change `get_agent_llm()` into `get_agent_llm(role=..., temperature=...)`.
- Add a role-to-profile map. Keep the profiles provider-agnostic.

Example:

```yaml
roles:
  orchestrator: high_reasoning
  critic: high_reasoning
  search_agent: cheap_tools
  travel_editor: cheap_tools
  booking_agent: cheap_tools
  chitchat: cheap_text

profiles:
  high_reasoning:
    gemini: gemini-2.5-pro
    dashscope: qwen-max
    openai: gpt-5
  cheap_tools:
    gemini: gemini-2.5-flash
    dashscope: qwen-turbo
    openai: gpt-5-mini
  cheap_text:
    gemini: gemini-2.5-flash-lite
    dashscope: qwen-turbo
    openai: gpt-5-nano
```

That gives you the structure you asked for:

- Orchestrator on a stronger model.
- Subagents on cheaper models.
- One config that still works when the active provider is Gemini, Qwen, or OpenAI.

If you want Gemini 3.1 for orchestration and Gemini 2.5 for subagents, that becomes a config change, not a code fork. If you switch to Qwen later, the role map stays the same and only the profile resolution changes.

What to change in code:

- Add a role enum or string literal set in `backend/llm.py`.
- Add `resolve_agent_llm_config(role)` and `get_agent_llm(role, ...)`.
- Pass explicit roles from each node.
- Keep a separate capability map for paths that need more than plain chat. Video analysis, tool calling, JSON mode, and browser-use all need slightly different guarantees.

Watch out:

- "Best model" is not just raw reasoning quality. The orchestrator needs strong planning and JSON reliability. The booking agent needs strong tool calling. The analyzer needs file and video support.
- Do not make role config depend on one provider's marketing names. Keep role names abstract and resolve them late.

### 5. Turn Trip.com into the first provider adapter

The booking layer is hard-coded to Trip.com in several places. The code says so directly.

`backend/agent/tools/booking_tools.py`

```python
provider_hint: str = "trip.com"
```

`backend/agent/nodes/booking_agent.py`

```python
"provider_hint": "trip.com",
```

`backend/services/automation/browser_use_worker.py`

```python
"https://www.trip.com/flights/showfarefirst/?..."
...
"Open https://www.trip.com and search booking options..."
...
"provider": "trip.com",
```

`backend/services/automation/playwright_checkout.py`

```python
def _is_trip_provider(self, provider: str, deeplink: str) -> bool:
    ...

async def _trip_checkout_flow(...):
    ...
```

`backend/agent/nodes/response_formatter.py`

```python
"已打开 trip.com 信息填充页，请在新窗口完成填写与支付。"
```

The tool surface is generic in name. The implementation is Trip.com flights with a few generic wrappers around it.

You do not need a hard-coded config file for every website on the internet. You do need site-specific support for every website you promise to support.

For reliable checkout, a plain config file is not enough. The search URL patterns, selectors, retries, baggage step, auth gates, and checkout pages all behave differently. Some pieces belong in config. The control flow still needs code.

What to do:

- Create a provider adapter boundary.

Example shape:

```python
class BookingProviderAdapter(Protocol):
    provider_id: str
    verticals: set[str]

    async def search(self, query, session) -> list[dict]: ...
    async def select_offer(self, page, offer) -> None: ...
    async def proceed_checkout(self, page, offer, traveler, skip_fill: bool) -> dict: ...
    def needs_auth(self, page) -> bool: ...
```

- Move the current Trip.com flight code into `TripFlightsAdapter`.
- Make `browser_use_worker` ask the registry for an adapter instead of building Trip.com URLs itself.
- Make `playwright_checkout` dispatch by adapter instead of by `_is_trip_provider`.
- Stop defaulting `provider_hint` to `"trip.com"`. Use `"auto"` or `None`.
- Make the formatter use `selected_offer["provider"]` instead of hard-coded Trip.com strings.

What should stay generic:

- Graph state.
- Offer schema.
- Booking session manager.
- Interrupt payloads.
- Chat UI.

What will stay site-specific:

- Search entry points.
- DOM selectors.
- Auth checks.
- Checkout branching.
- Deeplink validation.

I would start with three honest adapters, not one fake-generic layer:

- `TripFlightsAdapter`
- `TripTrainsAdapter` if you actually want trains next
- `BookingHotelsAdapter` or another hotel provider only after you pick one site to support

The fallback can stay generic. Search with browser-use if no adapter exists. Do not promise live checkout on that path.

### 6. Treat OpenAI Agents SDK as a separate runtime, not a LangGraph add-on

OpenAI Agents SDK does not use LangGraph under the hood. They are two separate orchestration runtimes.

- LangGraph gives you graph nodes, state, edges, and checkpoints.
- OpenAI Agents SDK gives you agents, handoffs, tool use, traces, and built-in MCP support.

Sources:

- [OpenAI Agents SDK overview](https://platform.openai.com/docs/guides/agents-sdk/)
- [OpenAI Agents SDK MCP support](https://openai.github.io/openai-agents-python/mcp/)

That means you have three sane options:

1. Keep LangGraph and do not migrate.
2. Keep LangGraph, but move reusable tools behind MCP so another runtime can call them later.
3. Move orchestration to OpenAI Agents SDK after the core tools are stable.

I would pick option 2 first. It gives you a migration path without rewriting the planner now.

If you add MCP here, add your own MCP servers around domain tools that the project already owns:

- `vacay-booking` MCP
  - `search_flights`
  - `select_offer`
  - `resume_checkout`
  - `get_booking_session_status`
  - `close_booking_session`
- `vacay-trips` MCP
  - `load_trip`
  - `save_trip`
  - `update_itinerary`
  - `list_trip_threads`
- `vacay-search` MCP
  - Tavily search
  - geocoding
  - image lookup
  - place normalization

These are worth building because either LangGraph or OpenAI Agents SDK could call them.

I would not add MCP just to say the app uses MCP. I would also not wrap everything in MCP on day one. Start with the tools that are already messy and already useful across runtimes: booking, trip state, and search.

For developer workflow, not product runtime, the most useful MCPs are different:

- OpenAI Docs MCP for SDK and API work.
- GitHub MCP for PR and issue triage.

Those help the team. They do not help the end user book travel.

### 7. Add real browser E2E coverage

This feature needs a standing regression suite.

- One test should stop at offer discovery.
- One should go through option selection.
- One should assert the handoff behavior and record whether the user lands on sign-in, passenger info, or another gate.
- One should cover provider compatibility for Gemini and DashScope/Qwen.
- One should prove session reuse if you adopt persistent browser profiles.

### 8. Make meal searches use the itinerary, not just the trip title

The lunch search has no idea where noon sits in the plan. It only gets the trip title as location context, so it searches a whole city or region and then asks the user to name an area or a nearby activity.

The problem is in `backend/agent/nodes/search_agent.py`. `_get_trip_city()` returns `trip.title`, and nothing in the search path looks at `time_slot`, the POI before lunch, or the POI after lunch. The orchestrator prompt says "include the city/area," but there is no code that computes that area from the itinerary.

What to do:

- Add a small helper that reads each day's `time_slot`s and finds the noon window.
- For meal requests, use the POI that ends before noon and the POI that starts after noon as the search anchor.
- Build the search query from those anchors. Example: `lunch near Villa del Balbianello / Bellagio ferry area`.
- If the user names a day, use that day. If chat history clearly refers to one day, use that day. If several days are equally plausible, ask `Day 2 or Day 3?` instead of `Which area?`
- Put this logic in code, not just in the prompt. The LLM should receive the chosen day and anchor area as facts.

Watch out:

- Some days will not have a clean noon gap. In that case, use the nearest POI before noon.
- If a day has no timed POIs at all, fall back to the trip title.

Tests:

- Lunch query on a trip with one noon gap uses the POIs before and after noon.
- Lunch query with two possible days asks which day, not which area.
- Dinner query uses evening anchors, not the noon window.

### 9. Put model and language settings in one editable YAML file

The project still spreads user-editable behavior across Python constants, environment defaults, and one JSON profile file. That makes simple changes harder than they should be. A user should not need to read `backend/llm.py` to change the orchestrator model or the assistant language.

Your direction is right. The app needs one editable config file for model choice and language, and the code should read from that file instead of carrying those choices as hard-coded defaults.

What to do:

- Add `config/config.yaml` as the editable app config.
- Move the role-to-model mapping from `backend/llm.py` into that YAML file.
- Move assistant language and fixed reply copy into that same YAML file.
- Make `backend/llm.py` a reader and resolver only. It should not define model names, role defaults, or language defaults.
- Keep secrets in `.env`. API keys do not belong in a user-facing YAML file.

What this file should hold:

```yaml
assistant:
  default_language: en
  supported_languages: [en, zh]
  copy:
    booking_missing_info:
      en: "I need exact airports and dates before I can search Trip.com."
      zh: "我需要准确的机场和日期才能查询 Trip.com。"

llm:
  provider_order: [dashscope, gemini]
  default_role: default
  roles:
    orchestrator: high_reasoning
    search_agent: cheap_tools
    booking_agent: cheap_tools
    critic: high_reasoning
  profiles:
    high_reasoning:
      gemini: gemini-2.5-pro
      dashscope: qwen-max
    cheap_tools:
      gemini: gemini-2.5-flash
      dashscope: qwen-plus
```

What to change in code:

- Add one config loader module that reads `config/config.yaml` and validates it.
- Make every agent prompt read `assistant.default_language` from that loader.
- Make `response_formatter.py` and `booking_agent.py` read fixed strings from the loader instead of embedding Chinese or English in code.
- Make `backend/llm.py` resolve `role -> profile -> provider model` from YAML, not from Python constants.
- Remove hard-coded fallback model names from `backend/llm.py`. If a role or provider is missing, fail with a clear config error.

What you asked for, in code terms:

- "Model choice should not be hard-coded" means the model name lives in YAML, not in `backend/llm.py`.
- "Model language should not be hard-coded" means prompt language and fixed reply language both live in YAML, not in node files.
- "All the code should refer to it" means nodes and helpers only call the config loader. They do not invent their own defaults.

Watch out:

- Secrets still need to stay in `.env`. The YAML should name providers and models, not carry API keys.
- If the YAML is incomplete, the app should fail fast with one clear message. Silent fallbacks will just recreate the current problem.

Tests:

- Changing `assistant.default_language` from `en` to `zh` changes booking replies without code edits.
- Changing the orchestrator profile in YAML changes the resolved model without code edits.
- Missing YAML keys fail with a clear validation error.

### 10. Use an LLM to normalize booking requests into a fixed schema

The booking bug is not that the system lacks a schema. The bug is that the schema is currently filled by regexes and tiny alias maps. That is why a normal follow-up message fails.

Your direction is the right one. The agent should use an LLM to read the user's travel request and turn it into a fixed booking object. The code still needs that fixed object before it calls tools, because tools need stable fields. The difference is where the structure comes from: the model, not hard-coded phrase matching.

What to do:

- Replace `_extract_route`, `_extract_date_iso`, and the airport alias map with one LLM normalization step.
- Give that step a strict output schema. Example fields: `origin`, `destination`, `departure_date`, `return_date`, `trip_type`, `adults`, `cabin`, `budget_limit`, `sort_preference`, `missing_fields`, `needs_clarification`.
- Run it at low temperature and require JSON output.
- If the model marks a field as missing or ambiguous, ask the user only for that field.
- Pass the normalized object straight into `find_booking_options`. Do not overwrite `return_date` or `adults` in code.

Example flow:

```text
user message
→ booking intent normalizer (LLM)
→ validated BookingIntent object
→ if complete: booking tool call
→ if incomplete: one precise follow-up question
```

What this changes from the old plan:

- No exact-phrase parser.
- No hard-coded airport alias map for cities and airports.
- No forced `return_date=""`.
- No forced `adults=1`.

How location resolution should work:

- First, let the normalizer preserve the user's place text as-is.
- If the destination is vague, run a second resolution step. This can use search plus geocoding, or a second LLM tool step that proposes likely airports from live search results.
- If the resolver finds one strong match, use it.
- If it finds several plausible airports, ask one follow-up question.

Why this still needs a schema:

- The browser tool cannot act on prose like "cheapest flight available next Sunday."
- It needs one object with dates, passenger count, trip type, and endpoints.
- The LLM should build that object. The tool layer should not guess it again.

What to change in code:

- Add a `BookingIntent` schema in Python.
- Add a booking normalizer helper that calls the LLM and returns `BookingIntent`.
- Call that helper from `booking_agent.py` before any booking tool call.
- Update `booking_tool_executor.py` so it trusts the normalized fields and never hard-codes missing values.
- Remove the alias-map guessing from `browser_use_worker.py`. Keep only UI-driving logic there.

What you asked for, in code terms:

- "It is an agent right?" means the model should do the intent understanding.
- "Why does it need a hard-coded parser?" It does not. It still needs a fixed output object, but the object should come from an LLM step.
- "Don’t hard-code return-date and number of adults" means the executor should only use what the normalized object contains, and ask the user when those fields are missing.

Watch out:

- LLM output still needs validation. Bad JSON or impossible dates should trigger one retry or one user question, not silent bad searches.
- A vague place like `Lake Como` may still need a clarification step if several airports are equally reasonable.

Tests:

- The exact screenshot text becomes a valid `BookingIntent` with round trip and two adults, or a single precise clarification if the destination is still ambiguous.
- A plain request like `from Singapore to Milan on 2026-04-19` still works.
- Missing return date for a round-trip request asks one follow-up instead of defaulting to empty.

### 11. Replace the single-line chat input with an auto-growing textarea

The chat box does not expand because it is not a textarea. `frontend/src/components/trip/ChatSidebar.tsx` renders `<Input>`, so the field is single-line by design.

What to do:

- Replace the `Input` in `ChatSidebar.tsx` with the existing `Textarea` component.
- Auto-resize it from content height on each change.
- Keep `Enter` to send and `Shift+Enter` to add a new line.
- Cap the height so the sheet does not collapse under a huge message.

Watch out:

- Reset the height after send, or the empty box stays tall.
- Do not break mobile keyboard behavior.

Tests:

- Typing multiple lines grows the input until the max height.
- `Enter` sends.
- `Shift+Enter` inserts a newline.

## Final Verdict

The new browser feature is real enough to demo. It is not yet honest enough to sell as a generic booking agent.

The strongest claim you can make today is this:

VACAY can search Trip.com flights from chat, show live options, take a choice, and drive a backend browser into the Trip.com pre-payment flow.

The claim you should not make yet is this:

VACAY can reliably bring the user straight into a live booking page on any site and let them finish checkout there.
