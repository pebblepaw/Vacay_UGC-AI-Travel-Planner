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

PUBLIC_URL=""
if [ -f "$ENV_PATH" ]; then
  PUBLIC_URL="$(grep -E '^PUBLIC_WEB_BASE_URL=' "$ENV_PATH" | tail -n 1 | cut -d'=' -f2- || true)"
fi

if [ -z "$PUBLIC_URL" ] || [ "$PUBLIC_URL" = "http://localhost" ] || [ "$PUBLIC_URL" = "https://localhost" ]; then
  EC2_PUBLIC_HOST="$(curl -fsS http://169.254.169.254/latest/meta-data/public-hostname 2>/dev/null || true)"
  if [ -n "$EC2_PUBLIC_HOST" ]; then
    PUBLIC_URL="http://${EC2_PUBLIC_HOST}"
  fi
fi

if [ -n "$PUBLIC_URL" ]; then
  printf '%s\n' "$PUBLIC_URL"
  exit 0
fi

echo "Stack started but no public URL was configured" >&2
exit 1
