# ScareVerse Backend Service Dockerfile
#
# Standalone container for the Backend API (FastAPI + uvicorn).
# Includes Gemini CLI (Node.js) for AI-assisted artifact generation.
# Replaces the unified supervisord-based container from infrastructure/scarerunner/.
#
# Ports:
#   5050 - Backend API (FastAPI/uvicorn)
#
# See: docker-compose.yml for runtime environment variables and volume mounts.

FROM python:3.11-slim

LABEL maintainer="ScareVerse Team"
LABEL description="ScareVerse Backend Service - FastAPI API + Gemini CLI"
LABEL version="1.0.0"

# System dependencies
# - curl: health checks
# - ca-certificates, gnupg: Node.js setup
# - nodejs: required for @google/gemini-cli
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Gemini CLI globally (stays in backend container per architecture decision)
RUN npm install -g @google/gemini-cli@latest

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

WORKDIR /app

# Install Python dependencies (cache layer - changes rarely)
COPY backend/requirements.txt ./backend-requirements.txt
RUN pip install --no-cache-dir -r backend-requirements.txt

# Copy backend application code
COPY backend/ ./backend/

# Create directories and fix permissions
RUN mkdir -p /app/artifacts /app/backend/logs \
    && chown -R appuser:appuser /app

# Expose Backend API port only
EXPOSE 5050

ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:5050/api/health || exit 1

# Copy entrypoint (handles UVICORN_RELOAD toggle)
COPY artifacts/canonical/services/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser

ENTRYPOINT ["/entrypoint.sh"]
