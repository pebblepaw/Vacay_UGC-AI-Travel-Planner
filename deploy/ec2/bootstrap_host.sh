#!/usr/bin/env bash
set -euo pipefail

sudo dnf install -y docker git tar gzip jq
sudo systemctl enable --now docker

if ! sudo docker compose version >/dev/null 2>&1; then
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

NEED_BUILDX=1
if sudo docker buildx version >/dev/null 2>&1; then
  CURRENT_BUILDX_VERSION="$(sudo docker buildx version | awk '{print $2}' | sed 's/^v//')"
  if [ "$(printf '%s\n' "0.17.0" "$CURRENT_BUILDX_VERSION" | sort -V | head -n 1)" = "0.17.0" ]; then
    NEED_BUILDX=0
  fi
fi

if [ "$NEED_BUILDX" -eq 1 ]; then
  BUILDX_URL="$(python3 - <<'PY'
import json
import urllib.request

data = json.load(urllib.request.urlopen("https://api.github.com/repos/docker/buildx/releases/latest"))
for asset in data["assets"]:
    name = asset["name"]
    if name.endswith("linux-amd64") and "provenance" not in name and "sbom" not in name:
        print(asset["browser_download_url"])
        break
else:
    raise SystemExit("Could not find buildx linux-amd64 asset")
PY
)"
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -SL "$BUILDX_URL" -o /usr/local/lib/docker/cli-plugins/docker-buildx
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
fi

sudo mkdir -p /opt/vacayclaw
sudo chown -R "$USER":"$USER" /opt/vacayclaw
