# ==============================================================================
# Claude Code Service Dockerfile
# ==============================================================================
# Base: node-pty-service image (já contém Node 20-slim, express, ws, ioredis,
# config pattern e Redis heartbeat infrastructure).
# Apenas adiciona entrypoint para download do Claude Code e server.js
# específico para Claude Code CLI.
# ==============================================================================

FROM hub-staging.scareverse.net/registry/staging/scareverse-node-pty-service:latest

# Substitui entrypoint e server para Claude Code
COPY entrypoint.sh /app/entrypoint.sh
COPY src/server.js /app/src/server.js
RUN chmod +x /app/entrypoint.sh && mkdir -p /app/claude-home

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
