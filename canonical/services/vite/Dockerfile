# ScareVerse Vite Service Dockerfile
#
# Standalone container for the Vite dev server.
# Compiles TypeScript/Vue components on-demand for dynamic cell/book types.
# Replaces the Vite process previously managed by supervisord.
#
# Port:
#   5052 - Vite dev server (HMR + on-demand compilation)
#
# Entrypoint:
#   Python script that starts heartbeat thread + npm run dev in foreground.
#
# See: docker-compose.yml for runtime environment variables and volume mounts.

FROM node:20-alpine

LABEL maintainer="ScareVerse Team"
LABEL description="ScareVerse Vite Service - dynamic TypeScript/Vue compilation"
LABEL version="1.0.0"

# curl for health checks; python3 + pip for heartbeat entrypoint
RUN apk add --no-cache curl python3 py3-pip

# Install redis-py for BaseService heartbeat (minimal dep - no pip venv needed)
RUN pip install --no-cache-dir --break-system-packages redis

# Create non-root user (Alpine-compatible syntax)
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app/artifacts

# Install Node.js dependencies at build time (Linux-native binaries)
# artifacts/canonical, shared, runtime etc. are mounted at runtime via volumes
COPY artifacts/package.json ./
COPY artifacts/tailwind.config.cjs ./
COPY artifacts/postcss.config.cjs ./
COPY artifacts/vite.config.ts ./
RUN npm install

# Fix permissions for non-root user (after install, before USER switch)
RUN chown -R appuser:appgroup /app/artifacts && chmod -R 755 /app/artifacts

# Copy heartbeat entrypoint
COPY artifacts/canonical/services/vite/entrypoint.py /app/entrypoint.py
RUN chmod +x /app/entrypoint.py

EXPOSE 5052

ENV NODE_ENV=development

# Health check: Vite responds to any HTTP request (even 404 = server is up)
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -s -o /dev/null http://localhost:5052/ || exit 1

USER appuser

CMD ["python3", "/app/entrypoint.py"]
