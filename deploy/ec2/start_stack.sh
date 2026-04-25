#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/vacayclaw}"
ENV_PATH="${2:-$APP_DIR/.env}"

if sudo docker compose version >/dev/null 2>&1; then
  COMPOSE=(sudo docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(sudo docker-compose)
else
  echo "Docker Compose is not available on the host" >&2
  exit 1
fi

cd "$APP_DIR"
"${COMPOSE[@]}" --env-file "$ENV_PATH" -f "$APP_DIR/docker-compose.yml" up --build -d

for _ in $(seq 1 90); do
  TUNNEL_URL="$("${COMPOSE[@]}" --env-file "$ENV_PATH" -f "$APP_DIR/docker-compose.yml" logs cloudflared 2>/dev/null | grep -Eo 'https://[-a-z0-9.]+trycloudflare.com' | tail -n 1 || true)"
  if [ -n "$TUNNEL_URL" ]; then
    printf '%s\n' "$TUNNEL_URL"
    exit 0
  fi
  sleep 2
done

echo "Failed to discover Cloudflare tunnel URL from container logs" >&2
exit 1
