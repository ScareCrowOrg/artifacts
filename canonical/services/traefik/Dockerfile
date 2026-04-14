FROM traefik:v3.1.0

# Install Python 3 and curl (curl for healthcheck, python3 for heartbeat)
RUN apk add --no-cache python3 py3-pip curl

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# ── Traefik static configuration ──────────────────────────────────────────────
COPY traefik.yml /app/traefik.yml

# ── Service code ──────────────────────────────────────────────────────────────
COPY ./config.py ./heartbeat.py /app/

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY ./entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ── Log directory ─────────────────────────────────────────────────────────────
RUN mkdir -p /app/logs

# Port 80: HTTP reverse proxy (public)
# Port 8080: Traefik dashboard / API (internal)
EXPOSE 80 8080

ENTRYPOINT ["/app/entrypoint.sh"]
