# Test Data

Use these inputs for manual testing. The same URLs also live in `Sample_Inputs/TikTok-Links.md`.

## Video Import URLs

| Description | URL |
|-------------|-----|
| 25 second video | `https://www.tiktok.com/@roadynz/video/7440193649578659090` |
| Single restaurant | `https://www.tiktok.com/@miaandtheworld/video/7506102845653962002` |
| Photo slides | `https://www.tiktok.com/@christinaelle_/photo/7544978045929622792` |
| 2.5 minute video | `https://www.tiktok.com/@ashlinpria/video/7595259514400673055` |

## Manual Chat Prompts

### Trip Editing
- `Find me a lunch place for Day 1`
- `Add a lunch location for Day 1`
- `Replan Day 1`
- `Optimize my trip`

### Flight Booking
- `Can you book me a flight from Singapore to this place on 2026-11-01 and back on 2026-11-07 for 2 people?`
- `offer_1`
- `Name: Jane Tan Email: jane@example.com Phone: +65 90000000`

## Expected Booking Behavior
- The agent should ask for missing flight details if the request is incomplete.
- When search works, the backend should return live Trip.com offers through chat.
- After selection, the backend should open or keep open a visible Playwright browser window.
- The flow should stop at the traveler or pre-payment page. It must not click final payment.
