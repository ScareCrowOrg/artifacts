#!/bin/bash
# ==============================================================================
# Nginx Unity – entrypoint.sh
# ==============================================================================
# Performs template substitution, validates Nginx config, starts Nginx in the
# background, then runs the FastAPI sidecar in the foreground (keeping the
# container alive).
#
# SIGTERM propagation: Docker sends SIGTERM to PID 1 (this script).  The trap
# below forwards the signal to both Nginx and the Python sidecar so both
# processes shut down gracefully before the container exits.
# ==============================================================================

set -e

# ── Defaults ──────────────────────────────────────────────────────────────────
export NGINX_PORT="${NGINX_PORT:-80}"
export CENTRALHUB_UPSTREAM="${CENTRALHUB_UPSTREAM:-centralhub:5051}"
export FRONTEND_UPSTREAM="${FRONTEND_UPSTREAM:-vite-frontend:5173}"
export SCARERUNNER_UPSTREAM="${SCARERUNNER_UPSTREAM:-scarerunner:5050}"
export GATEKEEPER_UPSTREAM="${GATEKEEPER_UPSTREAM:-gatekeeper:8000}"
export VITE_UPSTREAM="${VITE_UPSTREAM:-vite:5052}"
export BACKEND_UPSTREAM="${BACKEND_UPSTREAM:-backend:5050}"
export LOG_LEVEL="${LOG_LEVEL:-warn}"
# TUNNEL_FQDN: empty by default; set by orchestration Phase 7 when FQDN is known.
export TUNNEL_FQDN="${TUNNEL_FQDN:-}"
# NGINX_SERVER_NAME: used directly in server_name directive.
# Falls back to "_" (nginx catch-all) when TUNNEL_FQDN is not set.
export NGINX_SERVER_NAME="${TUNNEL_FQDN:-_}"

if [ -n "${TUNNEL_FQDN}" ]; then
    echo "[entrypoint] FQDN-aware routing enabled: ${TUNNEL_FQDN}"
else
    echo "[entrypoint] TUNNEL_FQDN not set – nginx will use catch-all server_name (_)"
fi

# ── Template substitution ─────────────────────────────────────────────────────
echo "[entrypoint] Substituting environment variables in nginx.conf.template..."
envsubst '$NGINX_PORT $CENTRALHUB_UPSTREAM $FRONTEND_UPSTREAM $SCARERUNNER_UPSTREAM $GATEKEEPER_UPSTREAM $VITE_UPSTREAM $BACKEND_UPSTREAM $LOG_LEVEL $TUNNEL_FQDN $NGINX_SERVER_NAME' \
    < /etc/nginx/nginx.conf.template \
    > /etc/nginx/nginx.conf

# ── Syntax validation ─────────────────────────────────────────────────────────
echo "[entrypoint] Validating Nginx configuration..."
nginx -t
echo "[entrypoint] Nginx configuration is valid."

# ── Start Nginx in background ─────────────────────────────────────────────────
# nginx daemonizes by default; run it explicitly in the background to capture PID.
nginx -g "daemon off;" &
NGINX_PID=$!
echo "[entrypoint] Nginx started (PID ${NGINX_PID})."

# ── Signal forwarding ─────────────────────────────────────────────────────────
_shutdown() {
    echo "[entrypoint] SIGTERM received – shutting down gracefully..."
    # Send SIGTERM to the Python sidecar (if running)
    if [ -n "${SIDECAR_PID}" ]; then
        kill -TERM "${SIDECAR_PID}" 2>/dev/null || true
    fi
    # Send SIGTERM to Nginx explicitly via captured PID
    if [ -n "${NGINX_PID}" ]; then
        kill -TERM "${NGINX_PID}" 2>/dev/null || true
    fi
    wait
    echo "[entrypoint] Shutdown complete."
}

trap _shutdown SIGTERM SIGINT

# ── Start FastAPI sidecar in foreground ───────────────────────────────────────
echo "[entrypoint] Starting FastAPI sidecar..."
python /app/main.py &
SIDECAR_PID=$!
echo "[entrypoint] FastAPI sidecar started (PID ${SIDECAR_PID})."

# Wait for the sidecar to exit (keeps the container alive)
wait "${SIDECAR_PID}"
