#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
mkdir -p /data/chromium-profile
rm -f \
  /data/chromium-profile/SingletonLock \
  /data/chromium-profile/SingletonSocket \
  /data/chromium-profile/SingletonCookie

pids=()

cleanup() {
  local status=$?
  for pid in "${pids[@]:-}"; do
    kill "${pid}" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit "${status}"
}

trap cleanup EXIT INT TERM

Xvfb "${DISPLAY}" -screen 0 1440x900x24 -ac +extension RANDR >/tmp/xvfb.log 2>&1 &
xvfb_pid=$!
pids+=("${xvfb_pid}")

display_ready=0
for _ in $(seq 1 30); do
  if xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
    display_ready=1
    break
  fi
  sleep 1
done

if [[ "${display_ready}" -ne 1 ]]; then
  echo "Xvfb did not become ready on ${DISPLAY}" >&2
  exit 1
fi

fluxbox >/tmp/fluxbox.log 2>&1 &
pids+=("$!")
x11vnc -display "${DISPLAY}" -forever -shared -rfbport 5900 -nopw >/tmp/x11vnc.log 2>&1 &
pids+=("$!")
websockify --web=/usr/share/novnc/ 7900 localhost:5900 >/tmp/novnc.log 2>&1 &
pids+=("$!")
socat TCP-LISTEN:9222,fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:9223 >/tmp/socat.log 2>&1 &
pids+=("$!")

CHROME_BIN="$(find /ms-playwright -path '*/chrome-linux/chrome' | head -n 1)"
if [[ -z "${CHROME_BIN}" ]]; then
  echo "Could not find Chromium in /ms-playwright" >&2
  exit 1
fi

"${CHROME_BIN}" \
  --no-sandbox \
  --disable-dev-shm-usage \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9223 \
  --user-data-dir=/data/chromium-profile \
  --window-size=1440,900 \
  about:blank >/tmp/chromium.log 2>&1 &
chrome_pid=$!
pids+=("${chrome_pid}")

wait "$chrome_pid"
