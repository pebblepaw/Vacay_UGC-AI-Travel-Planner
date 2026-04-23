# Agent Architecture (Plan-and-Execute Multi-Agent)

## Graph Flow

```
User Message
    |
+------------------+
|   ORCHESTRATOR    |  <-- Classifies intent + decomposes into plan steps
|  (Plan & Route)  |
+--------+---------+
         | conditional edges
         +---------------------+-------------------+-------------------+
         v                     v                   v                   v
+---------------+      +----------------+     +---------------+    +----------+
| TRAVEL EDITOR |      | SEARCH AGENT   |     | BOOKING AGENT |    | CHITCHAT | --> END
| (trip tools)  |      | (search_places)|     | (booking)     |    +----------+
+-------+-------+      +--------+-------+     +--------+------+
        v tool_calls?           v tool_calls?          v tool_calls?
+-----------------+    +------------------+    +------------------+
| TRAVEL TOOL     |    | SEARCH TOOL NODE |    | BOOKING TOOL     |
| EXECUTOR        |    | (standard)       |    | EXECUTOR         |
| (custom node)   |    +--------+---------+    | (custom node)    |
+-------+---------+             |              +--------+---------+
        v loop back             v loop back             v loop back
        +-------------+---------+-----------------------+
                      v
              +---------------+
              |    CRITIC     |  <-- Reflection: validates the last step
              +-------+-------+
                      | decision
          +-----------+-----------+
          v           v           v
       APPROVE     REVISE     CONFIRM
          v           v           v
    +----------+  back to    +-------------+
    | RESPONSE |  agent      | HUMAN       |
    | FORMATTER|             | REVIEW      |
    +----+-----+             | (interrupt) |
         v                   +------+------+
        END                         v
                                   END
```

## Patterns Demonstrated

| Pattern | Where | Description |
|---|---|---|
| **Supervisor/Router** | Orchestrator | Intent classification + plan decomposition |
| **Plan-and-Execute** | Orchestrator + State | Multi-step plans for editing, search, and booking |
| **Reflection/Critique** | Critic Node | Validates changes; auto-approves search-only steps |
| **Custom Tool Executor** | travel_tool_executor | Executes trip mutations with access to full trip state |
| **Custom Booking Executor** | booking_tool_executor | Executes booking tools and tracks offers, selection, and checkout status |
| **Standard Tool Calling** | Search Agent + ToolNode | Standard LangGraph `ToolNode` pattern |
| **Human-in-the-Loop** | Critic -> interrupt | LangGraph interrupt_before for destructive changes |
| **Bounded Iteration** | `iteration_count` in state | Prevents infinite loops. Current code auto-approves after 2 critic loops. |
| **Live Browser Handoff** | Booking executor + Playwright | Keeps a real Trip.com browser session alive when checkout needs the same session |

## Components (11 Nodes)

### 1. Orchestrator (orchestrator.py)
- **Role**: Classifies intent, decomposes complex requests into multi-step plans.
- **Logic**: Uses the configured `orchestrator` role model from `config/config.yaml`.
- **State**: Sets plan (list of steps), current_step, next_node (routing decision).
- **Mid-plan routing**: Uses keyword heuristics to route to travel, search, or booking agents.

### 2. Travel Editor (travel_editor.py)
- **Role**: ReAct agent with 6 trip-editing tools bound.
- **Tools**: delete_poi, add_poi, swap_poi, move_poi, replan_day, optimize_trip.
- **Context**: System prompt includes full trip with POI IDs and coords.
- **Flow**: Uses tools_condition to loop through tool calls -> custom executor.

### 3. Travel Tool Executor (travel_tool_executor.py)
- **Role**: Custom node that executes trip-modifying tool calls.
- **Key logic**:
  - _fetch_image(): Real photos via DuckDuckGo image search.
  - _balance_clusters(): Even POI distribution across days (<=4 per day).
  - _execute_replan_day(): Haversine-based travel_time with (0,0) coord guard.
  - haversine_km(): Distance calculation between POI coordinates.
- **Why custom?**: Needs access to trip state (standard ToolNode can't mutate state).

### 4. Search Agent (search_agent.py)
- **Role**: Finds places via search_places tool (Tavily + Nominatim).
- **Flow**: Standard ToolNode pattern.
- **Search context**: Includes trip city and can anchor meal searches near the right part of the day.

### 5. Search Tool Node (standard ToolNode)
- **Role**: Executes search_places tool calls automatically.

### 6. Booking Agent (booking_agent.py)
- **Role**: Handles booking requests, offer selection, and checkout.
- **Flow**:
  - Uses `normalize_booking_intent()` to turn the user request into a structured booking intent
  - Calls `find_booking_options`, `select_booking_option`, and `proceed_checkout`
  - Auto-routes to checkout after a valid offer selection
- **Current parsing split**:
  - Booking search request -> LLM normalization
  - Final traveler details -> regex extraction

### 7. Booking Tool Executor (booking_tool_executor.py)
- **Role**: Executes booking tools and updates booking state.
- **Key logic**:
  - stores booking offers and the selected offer in graph state
  - calls Playwright-backed search workers
  - opens checkout through `playwright_checkout.py`
  - preserves live Trip.com session handles when needed

### 8. Critic (critic.py)
- **Role**: Reflection node. Evaluates if the agent's changes are complete and correct.
- **Logic**:
  - Auto-approves search-only steps (no trip modifications expected).
  - Auto-approves after 2 iterations (current safety bound on `main`).
  - Routes: approve -> formatter, revise -> back to agent, confirm -> human_review.
  - **Current limitation**: still reads the first human message in history, not a durable current-request field.

### 9. Response Formatter (response_formatter.py)
- **Role**: Produces user-facing summary of changes.
- **Logic**:
  - resets `iteration_count` when advancing plan steps
  - turns booking offers into an interrupt payload for the frontend
  - turns checkout URLs or live-browser status into the final user-facing message
  - routes back to orchestrator for multi-step plans

### 10. Human Review (human_review.py)
- **Role**: LangGraph interrupt_before node for destructive changes beyond deletion threshold.

### 11. ChitChat (chitchat.py)
- **Role**: Handles greetings, thanks, and non-trip questions via direct LLM response.

## Configuration
- **Recursion limit**: 50 (set in chat.py's app.ainvoke())
- **Iteration bound**: Critic auto-approves after 2 loops on current `main`
- **Language**: `assistant.language` in `config/config.yaml`
- **Provider choice**: `llm.provider_preference` in `config/config.yaml`
- **Role-to-model mapping**: `llm.roles` and `llm.profiles` in `config/config.yaml`

## Tools

### Trip Tools
| Tool | Type | Description |
|---|---|---|
| delete_poi(poi_id) | Schema-only | Remove a POI by ID |
| add_poi(day, name, category, lon, lat, ...) | Schema-only | Insert a new POI |
| swap_poi(old_poi_id, new_name, ...) | Schema-only | Replace one POI with another |
| move_poi(poi_id, target_day) | Schema-only | Move POI between days |
| replan_day(day_number) | Schema-only | Algorithmic resequencing of a day |
| optimize_trip() | Schema-only | Cross-day geographic clustering + replan |
| search_places(query) | Real async | Tavily search + geocoding |

### Booking Tools
| Tool | Type | Description |
|---|---|---|
| find_booking_options(...) | Schema-only | Run live or fallback offer discovery |
| select_booking_option(option_id) | Schema-only | Pick one normalized offer from state |
| proceed_checkout(...) | Schema-only | Start checkout up to traveler/pre-payment step |

**"Schema-only"** means the tool has an `@tool` decorator for LLM binding, but execution happens in a custom executor node that has access to state.

## File Map

```
backend/agent/
  graph.py                    # StateGraph definition + edges
  state.py                    # AgentState TypedDict
  nodes/
    orchestrator.py           # Plan-and-execute router
    travel_editor.py          # ReAct agent with 6 tools
    travel_tool_executor.py   # Custom trip executor
    search_agent.py           # Search + ToolNode
    booking_agent.py          # Booking orchestration
    booking_tool_executor.py  # Custom booking executor
    critic.py                 # Reflection loop
    response_formatter.py     # User-facing output
    human_review.py           # HITL interrupt
    chitchat.py               # Small talk
  tools/
    trip_tools.py             # Trip and search tools
    booking_tools.py          # Booking tools
backend/services/
  booking_intent.py           # LLM booking normalization
  gemini_analyzer.py          # Video import via google.genai
  tavily_location.py          # Scope-aware geocoding
  automation/
    browser_use_worker.py     # Trip.com discovery worker
    playwright_checkout.py    # Checkout runner
    live_booking_sessions.py  # Live browser session registry
```

## Known Technical Debt
1. **Search-result selection is still brittle.** The structured interrupt + cached-selection version was rolled back. Search follow-ups still depend on prompt/context parsing.
2. **Critic state is incomplete.** It still judges against the first human message in history. The request-aware version was rolled back.
3. **Booking is Trip.com flight-first.** Other booking types are not at the same level of live automation.
4. **Checkout deep links are uneven.** Some fares still need a live session from the results page.
5. **Booking state is local memory.** `_BOOKING_SESSION` is not shared storage.
6. **Debug logging is verbose.** The `>>> NODE` logs are still always on.
