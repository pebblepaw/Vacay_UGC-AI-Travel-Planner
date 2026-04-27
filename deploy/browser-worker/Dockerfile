FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
    fluxbox \
    novnc \
    socat \
    websockify \
    x11-utils \
    x11vnc \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/browser-worker/start.sh /usr/local/bin/start-browser-worker.sh
RUN chmod +x /usr/local/bin/start-browser-worker.sh

EXPOSE 5900 7900 9222

CMD ["/usr/local/bin/start-browser-worker.sh"]
