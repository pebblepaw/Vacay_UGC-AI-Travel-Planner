# CS5260 Project Report: VacayClaw

## Team

- Zhang Jing Wen, A0328926R
- Song Hao Ran, A0329715X
- Peng Xianhan, A0331792B
- Hu Aoqi, A0329937L

GitHub: [Vacay_UGC-AI-Travel-Planner](https://github.com/pebblepaw/Vacay_UGC-AI-Travel-Planner)

## Summary

VacayClaw turns social travel videos into a shared trip workspace. A Telegram group and a web app control the same Supabase-backed trip, so users can import videos, edit the itinerary, review media folders, and hand off flight booking before payment.

The final version supports the full demo flow from Step 1 to Step 5. The user can send travel links, shrink the trip, ask for meal options, insert an activity, search for flights, choose an option, and receive a browser handoff link.

The main change from the early prototype is the runtime. The old product was a single-user web planner. VacayClaw is a collaborative agent runtime where Telegram and the website share the same state.

## Problem

Travel planning often starts with short-form videos. Users save TikToks, YouTube Shorts, Instagram posts, Douyin clips, and Rednote links, then paste them into a group chat. The useful information is scattered across video captions, speech, comments, locations, and friends’ messages.

This creates four problems.

First, the links do not become a trip. Someone still has to watch each clip, find the place, check whether it belongs in the route, and write it into an itinerary.

Second, the group chat is not a data model. It remembers discussion, but it does not preserve the current trip plan in a structured form.

Third, most planning tools are single-user. They do not treat the group chat as the main workspace.

Fourth, booking is disconnected from planning. The user has to leave the agent, search for flights, compare options, and stop before payment without losing context.

VacayClaw solves these problems by making the Telegram group the trip workspace.

## Final Product

VacayClaw has two control surfaces.

The first is Telegram. A user creates a group, adds `@VacayClawBot`, and sends a tagged message. The first tagged message creates or reuses a workspace with the ID pattern `telegram:{chat_id}:main`. Each workspace owns one trip.

The second is the web app. The bot returns a signed workspace link. Opening that link shows the same itinerary, map, chat history, and media folders. A message sent from the web app appears in Telegram as `Web user: ...`. Telegram messages appear in the web workspace through the same event stream.

Supabase stores the durable state: trips, workspaces, chat events, runtime state, media, and memory. The backend rebuilds workspace snapshots after state changes. The frontend reads those snapshots and subscribes to updates.

## Demo Flow

The final demo follows five steps.

Step 1 imports travel videos. The user sends TikTok, YouTube, Instagram, Douyin, or Rednote links. The backend detects the URLs, downloads or resolves the media where possible, analyzes the content, extracts places, and saves usable media data into the workspace. Each place card can show linked source videos.

Step 2 edits the trip length. The user can ask the bot to shrink the trip to two days. The agent updates the saved itinerary and returns the new workspace link.

Step 3 adds meals through selection. The user asks for lunch and dinner locations. The agent now returns options first instead of adding a restaurant immediately. The user can reply with `1`, `option 1`, or a place name. The selected restaurant is then added to the itinerary.

Step 4 inserts an activity. The user can ask for a stop such as a cinema visit. The agent updates the itinerary and keeps the saved trip consistent with the reply.

Step 5 handles flight booking. The user asks for a flight. The agent searches Trip.com and returns options with timing, airline or title, price, and dates. The user selects one option. The browser agent opens the traveler-details or payment-prep page and returns the current handoff URL. The system stops before payment.

## Architecture

VacayClaw uses a workspace-first backend.

The backend is a FastAPI service. It exposes Telegram webhook routes, workspace snapshot routes, chat routes, media ingestion routes, and booking handoff routes. The agent logic sits behind these routes and writes changes back to Supabase.

The frontend is a React and Vite app. It renders the workspace map, timeline, cards view, chat sidebar, and media overlay. It does not own the trip state. It reads the current workspace snapshot from the backend.

Supabase stores the shared state. The important records are workspaces, trips, conversation events, media items, workspace runtime state, memory entries, and share links.

This design keeps the group chat, web chat, itinerary, and booking state tied to one workspace. It avoids the old pattern where each browser session had its own private trip.

## Media Import

The media pipeline accepts travel links from multiple platforms. It detects supported URLs, resolves short links, downloads or opens media when allowed, and preserves the original source URL.

Gemini extracts places and descriptions from video content. Tavily, Mapbox, and OpenStreetMap help resolve place names, coordinates, and related metadata. The backend links each media item to the relevant place, so the frontend can show per-location media folders.

External platforms can still block access. Douyin and Rednote may require fresh cookies. When that happens, the system should fail cleanly and keep the rest of the workspace usable.

## Agent Design

VacayClaw uses the agent only where it creates value. It does not ask the model to own every state transition.

Simple routing uses deterministic checks. Media links trigger media import. Booking requests trigger flight search. Meal requests create pending options. Selection replies resolve pending meal or flight choices.

This makes the demo more stable. The agent can still generate summaries, extract intent, and reason over trip edits, but key product steps are backed by explicit runtime state.

The most important design rule is user control. The agent does not silently pick a restaurant or a flight when the user asked for options. It shows choices, stores the pending state, and waits for selection.

## Web Experience

The web app is built for desktop demo use. It shows the map and trip cards side by side, with chat as a shared control surface.

The cards page now supports media folders. Each location can show one or more linked media items. Clicking a media item opens an overlay. Playable files autoplay muted. Unsupported TikTok, Douyin, and Rednote embeds show a source-link card instead of an empty player.

This matters during the demo because the user can show the path from a saved video to a structured place card.

## Booking Handoff

Flight booking is scoped to handoff, not purchase.

The user asks for flights. The agent searches Trip.com. It returns a list of options. The user selects one. The browser agent opens the selected option and returns the current URL when it reaches traveler details, payment preparation, CAPTCHA, or another point that needs human control.

The product does not store payment details. It does not attempt to bypass CAPTCHA. It stops before payment.

## Evaluation

The final build was verified against the intended local demo path: local frontend, local backend, Telegram webhook delivery, and Supabase as the durable store.

The key behaviors are in place:

- A new Telegram group can create a workspace automatically.
- The workspace maps to one Supabase trip.
- The bot returns a signed web link for the same workspace.
- Web messages appear in Telegram as `Web user: ...`.
- Telegram messages appear in the web workspace.
- Media import supports the target link types.
- Trip edits update the saved itinerary.
- Meal and flight flows return options before selection.
- Flight booking returns a handoff URL and stops before payment.
- The cards page opens per-location media in an overlay.

Some live integrations depend on external services. Platform cookies, CAPTCHA, and webhook timeouts can affect a real run. The system is designed to preserve state and return control to the user when an external page blocks automation.

## Limitations

VacayClaw is a strong demo build, not a production travel agent.

Douyin and Rednote can require fresh cookies. The backend can handle supported links, but the platforms may refuse downloads in a live run.

Telegram can retry long webhook requests. A long media import may continue in the backend after Telegram has already retried the request. The duplicate reply path was reduced, but long-running imports should become background jobs in a production version.

Trip.com can show CAPTCHA or traveler-detail gates. The accepted behavior is to return the current URL and let the user continue manually.

The final demo path uses a local frontend and backend with Supabase for durable state. This keeps the setup simple and repeatable for the presentation.

## Conclusion

VacayClaw turns social travel inspiration into a shared trip. It connects the place where planning starts, Telegram, with the visual workspace users need to review and edit the plan.

The final contribution is the shared runtime. Media import, itinerary edits, meal selection, and flight handoff all operate inside one workspace. The user can move between Telegram and the web app without losing state.

That makes VacayClaw more than a prompt-based itinerary generator. It is a collaborative travel planning agent that keeps the group, the trip, and the booking handoff in one loop.
