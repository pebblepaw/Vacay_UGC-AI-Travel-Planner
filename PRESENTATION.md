# VacayClaw Presentation

## Slide 1: VacayClaw

Telegram-first travel planning from short-form videos.

- Import travel videos into a shared trip.
- Edit the same trip from Telegram or the web.
- Search flights and stop before payment.

Speaker note: VacayClaw turns the messy “send links in a group chat” workflow into a shared planning workspace.

## Slide 2: The Problem

Travel planning starts in social media, but the plan gets lost.

- Friends save TikToks, YouTube Shorts, Instagram posts, Douyin clips, and Rednote links.
- Each link has useful place information, but it is trapped inside media.
- Group chats contain the discussion, but not the trip state.
- Booking is a separate browser task with no agent handoff.

Speaker note: The project solves the gap between inspiration, shared decisions, itinerary edits, and booking handoff.

## Slide 3: Final Product

VacayClaw is a shared agent runtime for trip planning.

- One Telegram group creates one workspace.
- One workspace owns one trip in Supabase.
- The website opens the same workspace.
- The agent imports media, edits the itinerary, suggests meals, and searches flights.

Speaker note: The final version is not a single-user planner. It is a shared control surface across Telegram and the browser.

## Slide 4: Demo Flow

The final demo follows five user steps.

- Step 1: Import Sydney travel videos.
- Step 2: Shrink the trip to two days.
- Step 3: Ask for lunch and dinner options, then choose one.
- Step 4: Insert an activity such as a cinema stop.
- Step 5: Ask for flight options, choose one, and receive the handoff link.

Speaker note: The same steps can be sent from Telegram or the web chat. Both views stay synced.

## Slide 5: Shared Workspace Model

The workspace is the main product object.

- Workspace ID: `telegram:{chat_id}:main`.
- Telegram messages and web messages write to the same event log.
- Supabase stores the trip, chat events, runtime state, memory, and media.
- The frontend reads a signed workspace snapshot.

Speaker note: This removes the old single-session assumption. The group chat and web page now control the same state.

## Slide 6: Media Import Pipeline

VacayClaw turns links into itinerary data.

- Detects TikTok, YouTube, Instagram, Douyin, and Rednote URLs.
- Downloads or resolves media where the platform allows it.
- Uses Gemini to extract places and descriptions.
- Uses Tavily, Mapbox, and OpenStreetMap to resolve locations.
- Links each media item to the relevant place card.

Speaker note: The user can start from raw social links instead of typing a structured itinerary.

## Slide 7: Agent Behavior

The agent waits for user choice when choice matters.

- Meal requests return options first.
- The user selects by number or name.
- Flight requests return real options first.
- The user selects one option before browser handoff.
- The agent stops before payment.

Speaker note: The final behavior avoids silent auto-selection. The user keeps control at decision points.

## Slide 8: Web Experience

The web app is the visual workspace.

- Map and itinerary cards show the saved trip.
- Chat shows Telegram and web events.
- Media folders group videos by place.
- Clicking a media folder opens an overlay.
- Playable clips autoplay muted; unsupported sources show clean source links.

Speaker note: The web app is not a separate planner. It is the second control surface for the same workspace.

## Slide 9: Booking Handoff

Flight booking uses a browser agent.

- The user asks for flights.
- The agent searches Trip.com.
- The bot returns options with timing, airline, price, and dates.
- The user chooses an option.
- The agent opens the traveler or payment-prep page and returns the current URL.

Speaker note: CAPTCHA and passenger details are treated as handoff points. The project never completes payment.

## Slide 10: Verification

The final build focuses on the local demo path.

- Telegram group creation maps to a new Supabase workspace.
- Web and Telegram messages sync through workspace events.
- Step 1 media import supports the target platforms.
- Steps 2 to 4 update the saved itinerary.
- Step 5 returns flight options before handoff.
- The cards page supports per-location media playback.

Speaker note: External services can still block downloads or booking pages. The product returns the current URL when the browser must hand control back to the user.

## Slide 11: Limitations

The remaining limits come from external services and timeouts.

- Douyin and Rednote can require fresh cookies.
- Telegram can retry long webhook calls while imports continue.
- Trip.com can show CAPTCHA.
- The demo uses a local frontend and backend with Supabase as the durable store.

Speaker note: These are acceptable demo limits. The core workspace, sync, edit, import, and booking handoff paths are in place.

## Slide 12: Outcome

VacayClaw completes the travel planning loop.

- Inspiration becomes structured itinerary data.
- Group chat becomes a durable workspace.
- The web app gives a visual review surface.
- The agent handles edits and flight search.
- The user stays in control before payment.

Speaker note: The final contribution is a collaborative travel-agent runtime, not a prompt wrapper around a planner.
