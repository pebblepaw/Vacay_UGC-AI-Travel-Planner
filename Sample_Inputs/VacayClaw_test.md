# VacayClaw Manual E2E Script

Use these messages in `VacayClaw_26Apr` or a new Telegram group that contains `@VacayClawBot`.

For Telegram, paste each block as one message. Do not split the links across separate sends.

For the web app, paste the same text into the workspace chat box, without `@VacayClawBot`.

## Step 1: Import Sydney Media And Build A 3-Day Trip

```text
@VacayClawBot Plan a 3-day trip from these TikToks: 
1) https://www.tiktok.com/@hannahcockburnx/photo/7606527006515203350 
2) https://www.tiktok.com/@tom/video/7599581935580482837?q=sydney%20travel%20guide&t=1777053940679 
3) https://www.tiktok.com/@aimssimpson/video/7392550552560782624?is_from_webapp=1&sender_device=pc&web_id=7615950076326872597 
4) https://www.tiktok.com/@lizeandtom/video/7508677073490185494?is_from_webapp=1&sender_device=pc&web_id=7615950076326872597 
```

Check:

- The bot imports media once, not twice.
- The trip shows Sydney places with map pins.
- TikTok photo and video links both produce usable media metadata.
- Douyin is allowed to fail with a clear “failed” count if Douyin asks for fresh cookies.
- The workspace link opens the same trip in the local web app.

## Step 2: Shrink The Trip To 2 Days

```text
@VacayClawBot Shrink it to 2 days
```

Check:

- The bot says the trip is resized to 2 days.
- The web itinerary shows 2 days.
- Stops on each day are close enough to make sense.
- The route does not jump back and forth across Sydney without reason.

## Step 3: Ask For Meal Options

```text
@VacayClawBot Find lunch location for day one. 
```

Check:

- The bot shows options first.
- It does not add restaurants immediately.
- Each option includes a name, food type, day, meal slot, and rough area.

Then select one option:

```text
@VacayClawBot 1
```

Check:

- The selected restaurant is added to the itinerary.
- The web app updates to match Telegram.

Repeat selection if the bot shows another pending meal list.

## Step 4: Add The Cinema From A TikTok Caption

```text
@VacayClawBot Add this cinema: https://www.tiktok.com/@tessakvl/video/7595743816666254610
```

Check:

- The bot uses the caption to identify the cinema.
- The cinema appears in the itinerary.
- The source video appears in the place media folder.

## Step 5: Book A Flight

```text
@VacayClawBot Book a flight to Sydney for 2 pax, on the weekend of 2nd to 4th May
```

Check:

- The bot returns real Trip.com options.
- It does not auto-select a fare.

Then select one option:

```text
@VacayClawBot let's go with 1
```

Check:

- If Trip.com reaches traveler details, the bot returns that handoff URL.
- If Trip.com shows a CAPTCHA or verification wall, the bot returns `CAPTCHA encountered` with the current Trip.com URL. This counts as a pass for the demo.
- The bot must not loop or send repeated checkout messages for the same selection.

## Web Sync Check

Run one step from the web app instead of Telegram.

```text
Shrink it to 2 days
```

Check:

- Telegram receives a message like `Web user: Shrink it to 2 days`.
- The web app and Telegram show the same final trip.

## Cards Media Overlay Check

Open the local workspace link in a desktop browser.

Check:

- Mapbox renders.
- Cards view renders all places.
- Clicking a media folder opens an overlay.
- Playable videos autoplay muted with controls.
- Unsupported TikTok, Douyin, or Rednote links show a source-link card instead of an empty player.
