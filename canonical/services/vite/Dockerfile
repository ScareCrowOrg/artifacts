# ScareVerse Vite Service Dockerfile
#
# Standalone container for the Vite dev server.
# Compiles TypeScript/Vue components on-demand for dynamic cell/book types.
# Replaces the Vite process previously managed by supervisord.
#
# Port:
#   5052 - Vite dev server (HMR + on-demand compilation)
#
# See: docker-compose.yml for runtime environment variables and volume mounts.

FROM node:20-alpine

LABEL maintainer="ScareVerse Team"
LABEL description="ScareVerse Vite Service - dynamic TypeScript/Vue compilation"
LABEL version="1.0.0"

# curl for health checks
RUN apk add --no-cache curl

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app/artifacts

# Install Node.js dependencies at build time (Linux-native binaries)
# artifacts/canonical, shared, runtime etc. are mounted at runtime via volumes
COPY artifacts/package.json ./
COPY artifacts/tailwind.config.cjs ./
COPY artifacts/postcss.config.cjs ./
COPY artifacts/vite.config.ts ./
RUN npm install && chown -R appuser:appuser /app/artifacts

EXPOSE 5052

ENV NODE_ENV=development

# Health check: Vite responds to any HTTP request (even 404 = server is up)
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -s -o /dev/null http://localhost:5052/ || exit 1

USER appuser

CMD ["npm", "run", "dev"]
