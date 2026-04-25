#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
mkdir -p /data/chromium-profile

Xvfb "${DISPLAY}" -screen 0 1440x900x24 -ac +extension RANDR >/tmp/xvfb.log 2>&1 &
fluxbox >/tmp/fluxbox.log 2>&1 &
x11vnc -display "${DISPLAY}" -forever -shared -rfbport 5900 -nopw >/tmp/x11vnc.log 2>&1 &
websockify --web=/usr/share/novnc/ 7900 localhost:5900 >/tmp/novnc.log 2>&1 &

CHROME_BIN="$(find /ms-playwright -path '*/chrome-linux/chrome' | head -n 1)"
if [[ -z "${CHROME_BIN}" ]]; then
  echo "Could not find Chromium in /ms-playwright" >&2
  exit 1
fi

"${CHROME_BIN}" \
  --no-sandbox \
  --disable-dev-shm-usage \
  --remote-debugging-address=0.0.0.0 \
  --remote-debugging-port=9222 \
  --user-data-dir=/data/chromium-profile \
  --window-size=1440,900 \
  about:blank >/tmp/chromium.log 2>&1 &

wait -n
