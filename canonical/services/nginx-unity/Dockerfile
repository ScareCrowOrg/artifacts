# ==============================================================================
# Nginx Unity Service Worker
# ==============================================================================
# Two-process container:
#   1. Nginx reverse proxy   – handles all incoming HTTP routing
#   2. FastAPI health sidecar – health endpoints + Redis L1 heartbeat
#
# entrypoint.sh:
#   1. Runs envsubst on nginx.conf.template → nginx.conf
#   2. Validates config (nginx -t)
#   3. Starts Nginx in background
#   4. Starts FastAPI sidecar in foreground (keeps container alive)
# ==============================================================================

FROM nginx:alpine AS nginx-base

# Install Python 3, pip, and envsubst (gettext package provides envsubst)
RUN apk add --no-cache python3 py3-pip gettext curl bash

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# ── Nginx config template ─────────────────────────────────────────────────────
COPY nginx.conf.template /etc/nginx/nginx.conf.template

# ── Service code ──────────────────────────────────────────────────────────────
COPY config.py main.py /app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Health check (Nginx /health endpoint) ─────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${NGINX_PORT:-80}/health || exit 1

EXPOSE 80 9000

ENTRYPOINT ["/entrypoint.sh"]
