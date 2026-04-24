#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
WORKSPACE_ID="${WORKSPACE_ID:-telegram:demo-group:main}"

printf "\n[1/4] Sending workspace chat message...\n"
curl -sS -X POST "${API_BASE}/api/workspaces/${WORKSPACE_ID}/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message":"Plan flights from Singapore to Tokyo next month","source":"web"}' | jq .

printf "\n[2/4] Creating workspace share link...\n"
SHARE_JSON=$(curl -sS -X POST "${API_BASE}/api/workspaces/${WORKSPACE_ID}/share-link")
echo "$SHARE_JSON" | jq .
TOKEN=$(echo "$SHARE_JSON" | jq -r .token)

printf "\n[3/4] Fetching workspace snapshot...\n"
curl -sS "${API_BASE}/api/workspaces/${WORKSPACE_ID}/snapshot?token=${TOKEN}" | jq '.workspace_id, .updated_at'

printf "\n[4/4] Simulating Telegram webhook ingest...\n"
curl -sS -X POST "${API_BASE}/api/telegram/webhook" \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 1,
    "message": {
      "message_id": 10,
      "text": "Find cheaper flights",
      "chat": {"id": -100123, "title": "Vacay Demo"},
      "from": {"id": 9988, "username": "demo_user"}
    }
  }' | jq .

printf "\nDemo flow completed.\n"
