# ==============================================================================
# Traefik Service (Simplified – Multi-stage like Cloudflared)
# ==============================================================================
# Single-stage build (traefik:v3.1.0 is the base)
# Python is used only for heartbeat registration (fire-and-forget pattern)
# ==============================================================================

FROM traefik:v3.1.0

WORKDIR /app

# ── Install Python 3 and build tools for pip install ───────────────────────────
RUN apk add --no-cache python3 py3-pip gcc musl-dev python3-dev

# ── Python dependencies ────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# ── Remove build tools to keep image lean ──────────────────────────────────────
RUN apk del gcc musl-dev python3-dev

# ── Traefik static configuration ───────────────────────────────────────────────
COPY traefik.yml /app/traefik.yml

# ── Service code ───────────────────────────────────────────────────────────────
COPY heartbeat.py /app/heartbeat.py
RUN chmod +x /app/heartbeat.py

# ── Entrypoint ─────────────────────────────────────────────────────────────────
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ── Log directory ──────────────────────────────────────────────────────────────
RUN mkdir -p /app/logs

# Port 80: HTTP reverse proxy (public, replaces nginx-unity:80)
# Port 8080: Traefik dashboard / API (internal)
EXPOSE 80 8080

ENTRYPOINT ["/app/entrypoint.sh"]
