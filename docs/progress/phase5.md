# Phase 5: Advanced Agentic Itinerary Editor

**Status**: ✅ Completed (Feb 2025)  
**Goal**: Rebuild the LangGraph chatbot into a resume-worthy multi-agent system with reflection, tool calling, plan-and-execute, and human-in-the-loop patterns.

## Motivation

Phase 4 built a "Level 3 Orchestrator" — but it was a thin shell:
- Orchestrator just routes to 3 nodes, no multi-step planning.
- Travel Agent has 2 basic tools (`optimize_route`, `shorten_trip`) — can't add, delete, swap, or move POIs.
- Search Agent returns text, can't create structured POIs.
- No reflection loop — agent never self-checks its work.
- No human-in-the-loop — destructive changes happen silently.
- Route optimizer is greedy nearest-neighbor, per-day only.

Phase 5 rebuilds **everything** in the agent layer while keeping the rest of the stack (FastAPI, React frontend, JSON storage) untouched.

---

## Architecture

### New Graph Flow

```
User Message
    ↓
┌──────────────────┐
│   ORCHESTRATOR    │  ← Classifies intent + decomposes into plan steps
│  (Plan & Route)   │
└──────┬───────────┘
       │ conditional edges
       ├──────────────────────┐───────────────────┐
       ↓                      ↓                   ↓
┌─────────────┐      ┌──────────────┐     ┌──────────┐
│TRAVEL EDITOR│      │ SEARCH AGENT │     │ CHITCHAT  │→ END
│ (6 tools)   │      │ (Tavily)     │     └──────────┘
└─────┬───────┘      └──────┬───────┘
      ↓ tool_calls?          ↓ tool_calls?
┌─────────────────┐  ┌──────────────────┐
│TRAVEL TOOL EXEC │  │ SEARCH TOOL NODE │
│ (custom node)   │  │ (standard)       │
└─────┬───────────┘  └──────┬───────────┘
      ↓ loop back            ↓ loop back
      ↓ (until no more       ↓
      ↓  tool_calls)         ↓
      └──────────┬───────────┘
                 ↓
         ┌──────────────┐
         │    CRITIC     │  ← Reflection: validates changes
         │ (Self-Check)  │
         └──────┬───────┘
                │ decision
    ┌───────────┼───────────────┐
    ↓           ↓               ↓
 APPROVE     REVISE          CONFIRM
    ↓           ↓               ↓
┌────────┐  back to agent   ┌─────────────┐
│RESPONSE│  (with feedback) │HUMAN REVIEW │
│FORMATTER│  max 2 retries  │(interrupt)  │
└───┬────┘                  └──────┬──────┘
    ↓                              ↓
   END                            END
```

### Patterns Demonstrated

| Pattern | Where | Resume Value |
|---|---|---|
| **Supervisor/Router** | Orchestrator | Intent classification + plan decomposition |
| **Plan-and-Execute** | Orchestrator + State | Multi-step plans (e.g. "swap ramen for sushi" = delete + search + add) |
| **Reflection/Critique** | Critic Node | Validates timing, geography, intensity, completeness |
| **Custom Tool Executor** | `travel_tool_executor` | Shows understanding of LangGraph internals, not just prebuilt |
| **Standard Tool Calling** | Search Agent + ToolNode | Standard LangGraph pattern for comparison |
| **Human-in-the-Loop** | Critic → interrupt | LangGraph `interrupt_before` for destructive changes |
| **Bounded Iteration** | `iteration_count` in state | Prevents infinite loops (max 3) |
| **Hybrid LLM + Algorithm** | Optimizer tools | LLM decides *when/what*, algorithms execute *how* |

---

## Implementation Plan (8 Tasks)

### Task 1: State Enhancement
**File**: `backend/agent/state.py`
- Add `plan` as `list[str]` (multi-step)
- Add `current_step: int`
- Add `pending_changes: dict` (for HITL confirmation)
- Add `critique: str` (feedback from critic)
- Add `iteration_count: int` (bounded loops)
- Add `last_agent: str` (track which agent was active for critic routing)

### Task 2: New Tools
**File**: `backend/agent/tools/trip_tools.py` (full rewrite)
- `delete_poi(poi_id)` — remove a POI by ID
- `add_poi(day_number, name, category, longitude, latitude, ...)` — insert a new POI
- `swap_poi(old_poi_id, new_name, new_category, ...)` — replace one POI with another
- `move_poi(poi_id, target_day)` — move between days
- `replan_day(day_number)` — algorithmic resequencing (time-of-day heuristics + intensity balance + geography)
- `optimize_trip()` — cross-day optimizer (geographic clustering + day assignment + per-day replan)
- `search_places(query)` — Tavily + Nominatim, returns structured JSON

**Key Design**: Tools are `@tool`-decorated for LLM schema binding, but the execution for trip-editing tools happens in a **custom tool executor node** that has access to trip state. The LLM only passes small arguments (poi_id, day_number), never the full trip dict.

### Task 3: Orchestrator v2
**File**: `backend/agent/nodes/orchestrator.py` (rewrite)
- Decomposes complex requests into multi-step plans
- Example: "Replace the ramen with something more upscale" → `["search for upscale restaurants near Shinjuku", "swap poi_2 with best result"]`
- Better routing prompt with examples
- Handles `current_step` progression

### Task 4: Travel Editor Node
**File**: `backend/agent/nodes/travel_editor.py` (new, replaces `travel_agent.py`)
- Receives full trip context (with POI IDs) in prompt
- Bound to all 6 trip-editing tools
- Uses `tools_condition` to loop through tool calls
- Sends to `critic` when done (no more tool_calls)

### Task 5: Custom Travel Tool Executor
**File**: `backend/agent/nodes/travel_tool_executor.py` (new)
- Reads `tool_calls` from last AIMessage
- Reads trip from state
- Executes the actual logic (add/delete/swap/move/replan/optimize)
- Updates `trip` in state
- Returns `ToolMessage`s for the agent to see results

### Task 6: Search Agent v2
**File**: `backend/agent/nodes/search_agent.py` (rewrite)
- Uses Tavily + Nominatim for geocoded results
- Returns structured POI-compatible JSON (not just text)
- Standard ToolNode for execution (simple query → results)

### Task 7: Critic + Response Formatter + Human Review
**Files**: `backend/agent/nodes/critic.py`, `response_formatter.py`, `human_review.py` (all new)
- **Critic**: Evaluates modified trip for timing conflicts, geographic sanity, intensity balance, completeness
- **Response Formatter**: Produces clean user-facing summary of changes
- **Human Review**: Handles HITL interrupt for destructive operations

### Task 8: Graph Rewiring + Chat Router Updates
**Files**: `backend/agent/graph.py` (rewrite), `backend/routers/chat.py` (update)
- Rebuild graph with all new nodes and edges
- Add `interrupt_before=["human_review"]` for HITL
- Update chat router to handle interrupt state and trip persistence
- Add iteration bounds (max 3 loops)

---

## New Tool Details

### Optimizer Approach (Hybrid LLM + Algorithm)

**`replan_day`** — Pure algorithmic:
1. Assign time-of-day preferences by category (Nature→morning, Food→mealtimes, Nightlife→evening)
2. Sort within time blocks by geographic proximity
3. Assign `time_slot` values based on `visit_duration`
4. Intensity balancing: avoid consecutive high-intensity POIs

**`optimize_trip`** — Cross-day algorithmic:
1. Extract ALL POIs from all days
2. Geographic clustering (partition into N clusters, N = num days)
3. Assign clusters to days, preserving high-priority pinning where possible
4. Apply `replan_day` logic to each day
5. The **agent** (LLM) decides **when** to call these tools; the tools execute algorithmically

### Delete/Add/Swap/Move — Agent-Driven Selection

The **travel_editor LLM** sees the trip as formatted text with IDs:
```
Day 1:
  - [poi_1] TeamLab Borderless (Art) 10:00-13:00 | priority: high | intensity: normal
  - [poi_2] Shinjuku Gyoen Ramen (Food) 13:30-14:30 | priority: normal | intensity: normal
  - [poi_3] Shinjuku Gyoen Garden (Nature) 15:00-17:00 | priority: low | intensity: low
```

User says: "remove the ramen place"  
LLM reasons: "The ramen place is poi_2" → calls `delete_poi(poi_id="poi_2")`

No regex. No fuzzy matching. The LLM does the intent resolution.

---

## Files Changed/Created

| File | Action |
|---|---|
| `backend/agent/state.py` | Modified |
| `backend/agent/tools/trip_tools.py` | Rewritten |
| `backend/agent/nodes/orchestrator.py` | Rewritten |
| `backend/agent/nodes/travel_editor.py` | **New** (replaces `travel_agent.py`) |
| `backend/agent/nodes/travel_tool_executor.py` | **New** |
| `backend/agent/nodes/search_agent.py` | Rewritten |
| `backend/agent/nodes/critic.py` | **New** |
| `backend/agent/nodes/response_formatter.py` | **New** |
| `backend/agent/nodes/human_review.py` | **New** |
| `backend/agent/graph.py` | Rewritten |
| `backend/routers/chat.py` | Updated |
| `backend/tests/test_agent_e2e.py` | **New** |

---

## Testing Strategy

E2E tests using real LLM calls against a test trip:
1. **Delete**: "Remove the ramen spot" → verify poi_2 is gone
2. **Add**: "Add a sushi restaurant to Day 1" → verify new POI exists
3. **Swap**: "Replace TeamLab with a museum" → verify swap
4. **Move**: "Move the garden to Day 2" → verify day change
5. **Optimize**: "Optimize my route" → verify reordering
6. **Multi-step**: "Replace ramen with something fancier" → verify search + swap
7. **Reflection**: Verify critic catches timing conflicts
8. **Chitchat**: "Hello" → verify routing to chitchat

---

## Dependencies

```
langgraph==0.6.11
langchain-core==0.3.83
langchain-google-genai==2.0.10
tavily-python
duckduckgo-search   # For image fetching + web search fallback
```

---

## Post-Implementation Fixes

After the full rebuild was deployed, live testing revealed several bugs that were fixed:

### Dependency Conflicts
Aligned `langchain-core`, `langchain-google-genai`, and `langgraph` to compatible versions.

### Missing `latitude` in `add_poi`
Tool schema was missing `latitude: float`, causing Gemini to hallucinate the parameter.

### Missing `next_node` in `AgentState`
`AgentState(TypedDict)` didn't include `next_node`, so the orchestrator's routing was silently dropped — all messages went to chitchat. Fixed by adding `next_node: str` to state.

### Critic Loop → `GraphRecursionError`
Critic kept saying "revise" on search-only steps (no trip changes made). Fixed by auto-approving search steps and resetting `iteration_count` between plan steps. Recursion limit raised from 25 → 50.

### Gemini JSON Parsing Failure
Gemini returned JSON wrapped in preamble text + markdown fences. The parser only checked `startswith("```json")`. Fixed with 3-tier extraction: direct parse → regex fence extraction → outermost `{...}` brace matching.
