<p align="center">
  <img width="1600" alt="ig_0ada80e07f82dbff0169f0a8bc3a2481918e8543d4343c5a11" src="https://github.com/user-attachments/assets/b754fe22-f678-44f4-9c8f-27f2c241f148" />
</p>
<!-- <h1 align="center">VacayClaw</h1> -->
  <p align="center">
        <a href="https://youtu.be/Dha7aI1RXJg"><img src="https://img.shields.io/badge/YouTube-Demo-FF0000?logo=youtube&logoColor=white" alt="YouTube Demo" /></a></p>
        
## Overview

VavayClaw is an **AI-powered travel planner** that turns short-form travel videos (TikTok, Douyin, YouTube Shorts) into interactive, editable itineraries. 

Make a **Telegram group** with your friends, add the @VavayClawBot, send it TikToks, and VACAY automatically extracts locations, builds a day-by-day trip plan, pins everything to the map, and lets you see it on a hosted dashboard. 

Once you're happy with the plan, ask VavayClaw to **book the flight** for you as well! 

## What It Does

- Imports TikTok, YouTube, Instagram, Douyin, and Rednote links into one shared workspace.
- Uses LLM API to extract places from media.
- Uses **Tavily, Mapbox, and OpenStreetMap** to verify and find new locations. 
- Builds a day-by-day itinerary with map markers, timeline cards, and per-location media folders.
- Syncs Telegram group messages and web chat through the same workspace event log.
- Searches real **Trip.com** flight options, waits for user selection, and returns a browser handoff before payment.
- Stores trips, workspace state, chat events, and memory in **Supabase** backend. 

## Demo 

<table align="center">
  <tr>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/fa1378a8-916b-4ef5-96c2-d10116a9fb36" width="600"/><br/>
      <sub><b>Travel Itinerary</b></sub>
    </td>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/0e7a132d-dc5d-410a-8228-9e323aff93d3" width="600"/><br/>
      <sub><b>Uploaded Media</b></sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/748941b2-7057-463f-aecc-9b1e786c8714" width="600"/><br/>
      <sub><b>Watch Media</b></sub>
    </td>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/8a8f309c-8239-4bc1-ace0-12b0a24350cd" width="600"/><br/>
      <sub><b>Control through Telegram</b></sub>
    </td>
  </tr>
</table>

<p align="center">
  <a href="https://youtu.be/hMA_ZYjBpuI">
     <b>Click here to watch the full demo here</b>
  </a>
</p>

## How it works


<img width="900" alt="ig_065bda5d330e23b60169ef6d10939c8191886d5efe4effbfff" src="https://github.com/user-attachments/assets/5c921edb-aed4-4b8d-9289-5be86e37726f" />


<img width="900" alt="ig_065bda5d330e23b60169ef704c5b5081919d54671846381361" src="https://github.com/user-attachments/assets/c49ba794-2b64-4c8c-892f-5bbcf917a4e0" />


## Requirements

- Python 3.11+
- Node.js 18+
- Supabase project with the tables used by this repo
- API keys for Gemini, Tavily, and Mapbox
- Optional: Telegram bot token and `cloudflared` for group-chat demos

## Install

```bash
git clone https://github.com/pebblepaw/Vacay_UGC-AI-Travel-Planner.git
cd Vacay_UGC-AI-Travel-Planner

python3 -m venv venv
source venv/bin/activate
python -m pip install -r backend/requirements.txt

cd frontend
npm install
cd ..
```

Create `.env` in the repo root. See [docs/brd/env_vars.md](docs/brd/env_vars.md) for the full list.

Minimum local demo keys:

```bash
GEMINI_API_KEY=...
TAVLY_API=...
MAPBOX_PUBLIC=...
MAPBOX_SECRET=...
SUPABASE_PROJECT_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SECRET_KEY=...
```

Telegram demo keys:

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...
```

## Run Locally

```bash
./start.sh
```

Default URLs:

- Frontend: [http://127.0.0.1:8080](http://127.0.0.1:8080)
- Backend: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Change ports if needed:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=3000 ./start.sh
```

## Use our Demo Inputs

Telegram needs a public HTTPS webhook. For local demos, use the built-in Cloudflare quick tunnel:

```bash
TELEGRAM_TUNNEL=1 ./start.sh
```

Then:

1. Create a Telegram group.
2. Add `@VacayClawBot`.
3. Send a tagged message, for example `@VacayClawBot plan this trip ...`.
4. The first tagged message creates a Supabase workspace with ID `telegram:{chat_id}:main`.
5. Open the workspace link returned by the bot to control the same trip in the browser.

Use [Sample_Inputs/VacayClaw_test.md](Sample_Inputs/VacayClaw_test.md) for copy-paste demo messages.

## Project Structure

```text
backend/                 FastAPI backend, agent graph, services, routers
frontend/                React + Vite frontend
config/config.yaml       Model routing and user-facing booking copy
Sample_Inputs/           Manual Telegram and web E2E prompts
deploy/                  Docker, Nginx, and worker deployment files
```
