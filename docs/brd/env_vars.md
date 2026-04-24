# Environment Variables

The app uses two config surfaces:

- `.env` for secrets and service URLs
- `config/config.yaml` for assistant language, provider preference, and role-to-model mapping

Do not commit `.env`.

```bash
# LLM providers
GEMINI_API_KEY=...          # Required for video import, optional for agent chat if using DashScope
DASHSCOPE_API_KEY=...       # Optional. Enables Qwen/DashScope agent models
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Search / maps
TAVLY_API=...               # Tavily API key. The code uses the name TAVLY_API.
MAPBOX_PUBLIC=...           # Frontend map token
MAPBOX_SECRET=...           # Backend geocoding token

# Storage
SUPABASE_PROJECT_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SECRET_KEY=...     # Service-role key for backend access

# Optional runtime flags
APP_CONFIG_PATH=config/config.yaml
BOOKING_STRICT_REAL_TRIP=true
DEBUG=true
```

## What Lives In `config/config.yaml`
- `assistant.language`
- `llm.provider_preference`
- `llm.roles`
- `llm.profiles`
- fixed booking copy shown to users

## Notes
- `start.sh` reads `.env`, then exports `VITE_MAPBOX_PUBLIC` to the frontend.
- If `DASHSCOPE_API_KEY` is missing, the agent falls back to Gemini when Gemini is configured.
- Video import still needs `GEMINI_API_KEY` because the analyzer uses `google.genai`.
