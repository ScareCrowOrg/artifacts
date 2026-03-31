# ==============================================================================
# Nginx Unity Service Worker
# ==============================================================================
# Two-process container:
#   1. Nginx Unit reverse proxy – handles all incoming HTTP routing via HTTP API
#   2. FastAPI heartbeat sidecar – Redis L1 heartbeat registration
#
# entrypoint.sh:
#   1. Waits for Nginx Unit API to be ready (port 8080)
#   2. Starts FastAPI sidecar in foreground (keeps container alive)
#
# Routes are registered dynamically via the Nginx Unit HTTP API after services
# become available (heartbeat-driven via Node.js sidecar).
# ==============================================================================

FROM nginx/unit:latest

# Fix Debian Buster (EOL) apt sources
RUN sed -i 's|http://deb.debian.org|http://archive.debian.org|g' /etc/apt/sources.list && \
    sed -i '/debian-security/d' /etc/apt/sources.list

# Install Python 3, pip, and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install --no-cache-dir -r requirements.txt

# ── Nginx Unit initial config (minimal, no upstreams) ─────────────────────────
COPY unit.conf.json /docker-entrypoint.d/unit.conf.json

# ── Service code ──────────────────────────────────────────────────────────────
COPY config.py main.py /app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Expose Nginx Unit HTTP port and Unit API port ─────────────────────────────
EXPOSE 80 8080

ENTRYPOINT ["/entrypoint.sh"]
