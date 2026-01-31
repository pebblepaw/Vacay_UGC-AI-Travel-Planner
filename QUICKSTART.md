# 🚀 VACAY Quick Start Guide

You've successfully built a fully functional AI-powered travel planner! Here's how to test it.

## ✅ What You Built

A complete full-stack application that:
- Downloads videos from TikTok/YouTube using yt-dlp
- Analyzes them with Google Gemini 1.5 Pro to extract locations
- Geocodes locations with Tavily API
- Builds day-by-day travel itineraries
- Provides an AI chat assistant
- Beautiful React frontend with maps, timeline, and card views

## 🏃 Running the App

### Option 1: Use the Startup Script (Recommended)
```bash
./start.sh
```

This automatically starts both backend and frontend.

### Option 2: Manual Start

**Terminal 1 - Backend:**
```bash
source venv/bin/activate
python -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## 📍 Access Points

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)

## 🎬 Testing the App

### 1. Using the Frontend

1. Open http://localhost:5173
2. Click the **+** button (bottom left)
3. Paste a TikTok or YouTube URL:
   - Example: `https://www.tiktok.com/@roadynz/video/7440193649578659090`
   - More test URLs in `Sample_Inputs/TikTok-Links.md`
4. Click "Process Video"
5. Wait 30-60 seconds for processing
6. You'll be redirected to your new trip!

### 2. Testing Chat

1. Click the chat icon (bottom right)
2. Ask questions like:
   - "Tell me about the accommodation"
   - "Show me food options"
   - "How many days is this trip?"
   - "What's the budget?"

### 3. Using the API Directly

**Process a video:**
```bash
curl -X POST http://localhost:8000/api/videos/process \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://www.tiktok.com/@roadynz/video/7440193649578659090"],
    "trip_title": "My Tokyo Adventure"
  }'
```

**List all trips:**
```bash
curl http://localhost:8000/api/trips
```

**Get specific trip:**
```bash
curl http://localhost:8000/api/trips/trip_abc123
```

**Send chat message:**
```bash
curl -X POST http://localhost:8000/api/trips/trip_abc123/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about food options"}'
```

## 🧪 Running Tests

**Backend integration test:**
```bash
source venv/bin/activate
python backend/tests/test_integration.py
```

**Frontend tests:**
```bash
cd frontend
npm test
```

## 📁 Where Your Data Lives

- **Downloaded Videos**: `/downloads` (temporary, auto-deleted after processing)
- **Trip Data**: `/backend/data/trips/*.json` (one JSON file per trip)
- **Environment Variables**: `/.env` (API keys)

## 🐛 Troubleshooting

### "Failed to download video"
- Check if the URL is accessible
- Some TikTok videos require cookies (not implemented yet)
- Try a different video URL

### "Gemini API error"
- Verify `GEMINI_API_KEY` in `.env` is correct
- Check you have API quota remaining
- Video may be too large (500MB limit)

### "Failed to geocode location"
- Tavily API key may be invalid
- Falling back to Nominatim (OpenStreetMap) - works but no images

### Frontend shows "Trip not found"
- Make sure backend is running on port 8000
- Check VITE_API_URL in `frontend/.env`
- Try processing a new video

## 🔑 API Keys Reminder

Make sure your `.env` file has:
```bash
GEMINI_API_KEY=AIza...     # Get from: https://makersuite.google.com/app/apikey
TAVLY_API=tvly-...         # Get from: https://tavily.com/
MAPBOX_PUBLIC=pk.eyJ...    # Get from: https://www.mapbox.com/
MAPBOX_SECRET=sk.eyJ...    # Get from: https://www.mapbox.com/
```

## 🎯 Next Steps

Your core implementation is complete! Consider:

1. **Test with Real Videos**: Try different TikTok/YouTube travel videos
2. **Improve Prompts**: Edit `backend/services/gemini_analyzer.py` to get better location extraction
3. **Add More Features**: See `BRD.md` Phase 2 for ideas (Supabase, LangChain, Playwright)
4. **Deploy**: Deploy backend to Railway/Render and frontend to Vercel/Netlify

## 📚 Documentation

- **BRD.md**: Complete implementation guide with all tasks
- **PROGRESS.md**: Development log with learnings and patterns
- **README.md**: Project overview and setup instructions

## 🎉 Congratulations!

You've built a complete AI-powered travel planner from scratch. The system:
- ✅ Downloads and analyzes videos
- ✅ Extracts and geocodes locations
- ✅ Generates beautiful itineraries
- ✅ Provides AI chat assistance
- ✅ Has a polished React frontend

Enjoy exploring and extending your creation! 🌴
