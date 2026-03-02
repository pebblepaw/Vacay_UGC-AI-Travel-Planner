# VACAY

> Transform TikTok travel videos into actionable travel itineraries with AI

VACAY is an AI-powered travel planner that takes short-form travel videos (TikTok, YouTube Shorts) and automatically extracts locations, creates day-by-day itineraries, and displays them on an interactive map.

## Table of Contents

1. [Key Features](#features)  
2. [Demo Video](#demo-video)  
3. [Quick Start](#quick-start)
4. [Project Structure](#project-structure)
5. [Tests](#testing)
6. [Architectural Diagrams](#architectural-diagrams)
7. [Tech Stack](#tech-stack)

## Features

- **Video Processing**: Paste a TikTok URL and watch as AI extracts all the travel spots
- **Smart Itinerary Building**: Locations are automatically clustered by proximity and organized into days
- **Interactive Maps**: See all your destinations on a Mapbox map with route visualization
- **AI Chat**: Refine your itinerary by chatting with the AI assistant

## Demo Video
<video src="https://github.com/user-attachments/assets/862660d9-cfae-4a80-ba3c-4c1583b5342c" width="320" height="240" controls></video>

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- API Keys (see below)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/pebblepaw/Vacay_UGC-AI-Travel-Planner.git
   cd Vacay_UGC-AI-Travel-Planner
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start the backend**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   cd backend
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

4. **Start the frontend** (in a new terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Open the app**
   - Frontend: http://localhost:5173
   - API Docs: http://localhost:8000/docs

### Required API Keys

| Service | Purpose | Get it at |
|---------|---------|-----------|
| Gemini | Video analysis | [Google AI Studio](https://aistudio.google.com/) |
| Tavily | Location search | [Tavily](https://tavily.com/) |
| Mapbox | Maps | [Mapbox](https://mapbox.com/) |

## Project Structure

```
VACAY/
├── backend/          # Python FastAPI server
│   ├── services/     # Video download, AI analysis, geocoding
│   ├── routers/      # API endpoints
│   └── models/       # Pydantic schemas
└── frontend/         # React + Vite + Shadcn UI
    └── src/
        ├── components/
        ├── contexts/
        └── services/
```

## Testing

```bash
# Backend tests
cd backend
python -m pytest tests/ -v

# Frontend tests
cd frontend
npm test
```

## Architectural Diagrams

**Overview**

<img width="400" height="1024" alt="00_user_flow" src="https://github.com/user-attachments/assets/9cd9a14e-d761-44d3-94a8-930695550633" />


**Agentic Chat LangGraph Design**

<img width="400" height="1024" alt="02_langgraph_agent_loop" src="https://github.com/user-attachments/assets/2ed434e7-f157-415c-8e60-b8b193b338c6" />


## Tech Stack
<img width="400" height="1024" alt="01_system_architecture" src="https://github.com/user-attachments/assets/db373942-773e-4aed-b169-1f85d300b1c6" />


**Frontend**
- React 18 + TypeScript
- Vite
- Tailwind CSS + Shadcn UI
- Framer Motion
- Mapbox GL JS

**Backend**
- Python 3.11+
- FastAPI
- yt-dlp (video downloading)
- Google Gemini 1.5 Pro (AI analysis)
- Tavily (location search)
