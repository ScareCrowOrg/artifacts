# ==============================================================================
# Cloudflared Service Worker
# ==============================================================================
# Two-stage Docker image:
#   1. cloudflared binary  – obtained from the official cloudflare/cloudflared image
#   2. python:3.11-slim    – FastAPI health sidecar
#
# The entrypoint launches cloudflared tunnel (if TUNNEL_TOKEN is set) in the
# background and then runs the FastAPI sidecar in the foreground.
# ==============================================================================

FROM cloudflare/cloudflared:latest AS cloudflared-bin

FROM python:3.11-slim

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps curl \
    && rm -rf /var/lib/apt/lists/*

# ── Copy cloudflared binary ───────────────────────────────────────────────────
COPY --from=cloudflared-bin /usr/local/bin/cloudflared /usr/local/bin/cloudflared

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Service code ──────────────────────────────────────────────────────────────
COPY config.py main.py ./

# ── Artifacts (BaseService) ───────────────────────────────────────────────────
# Mounted at runtime via docker-compose volume; copied here for image builds
# that include artifacts in build context.
# COPY ../../../.. /app/artifacts  ← provided by compose volume mount

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${HEALTH_PORT:-8000}/health || exit 1

EXPOSE 8000

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Start cloudflared tunnel in background (if token is present), then run sidecar.
CMD ["/bin/bash", "-c", \
    "if [ -n \"${TUNNEL_TOKEN}\" ]; then \
        cloudflared tunnel --no-autoupdate run --token \"${TUNNEL_TOKEN}\" & \
        echo \"Cloudflared tunnel started (PID $!)\"; \
    else \
        echo \"TUNNEL_TOKEN not set – running in health-only mode\"; \
    fi; \
    exec python main.py"]
