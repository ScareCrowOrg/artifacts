# ==============================================================================
# Cloudflared Service (Simplified)
# ==============================================================================
# Three-stage Docker image:
#   - Stage 1 (cloudflared-bin): Extract cloudflared binary from official image
#   - Stage 2 (python-deps): Install Python dependencies for BaseService
#   - Stage 3 (final): Alpine + cloudflared + Python + heartbeat.py
#   - No FastAPI, no uvicorn – just heartbeat + tunnel
# ==============================================================================

FROM cloudflare/cloudflared:latest as cloudflared-bin

# ==============================================================================
# Stage 2: Build Python dependencies
# ==============================================================================

FROM python:3.11-slim as python-deps
RUN pip install --no-cache-dir redis httpx

# ==============================================================================
# Final stage: Python 3.11 Alpine + cloudflared + heartbeat
# ==============================================================================

FROM python:3.11-alpine

WORKDIR /app

# ── Copy cloudflared binary from official image ────────────────────────────────
COPY --from=cloudflared-bin /usr/local/bin/cloudflared /usr/local/bin/cloudflared

# ── Copy Python dependencies from builder ──────────────────────────────────────
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# ── Heartbeat script ───────────────────────────────────────────────────────────
COPY heartbeat.py /app/heartbeat.py
RUN chmod +x /app/heartbeat.py

# ── Entrypoint script ──────────────────────────────────────────────────────────
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ── Environment ───────────────────────────────────────────────────────────────
# All variables are injected at runtime via docker-compose env or -e flags:
#   TUNNEL_TOKEN       – Cloudflare tunnel token (optional; set after tunnel creation)
#   TUNNEL_NAME        – Planet name

# ── Entrypoint ────────────────────────────────────────────────────────────────
ENTRYPOINT ["/app/entrypoint.sh"]
