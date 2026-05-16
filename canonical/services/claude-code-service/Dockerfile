# ==============================================================================
# Claude Code Service Dockerfile
# ==============================================================================
# Base: node-pty-service image (já contém Node 20-slim, express, ws, ioredis,
# config pattern e Redis heartbeat infrastructure).
# Apenas adiciona entrypoint para download do Claude Code e server.js
# específico para Claude Code CLI.
# ==============================================================================

FROM hub-staging.scareverse.net/registry/staging/scareverse-node-pty-service:latest

# Safety: garantir que CA certificates estão instalados (base image pode estar sem)
# node:20-slim não inclui ca-certificates, e builds anteriores do node-pty-service
# podem ter o pacote em estado "unpacked not configured" — isso quebra curl HTTPS.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Substitui entrypoint e server para Claude Code
COPY entrypoint.sh /app/entrypoint.sh
COPY src/server.js /app/src/server.js
RUN chmod +x /app/entrypoint.sh && mkdir -p /app/artifacts

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
