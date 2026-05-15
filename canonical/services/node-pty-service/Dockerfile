# ==============================================================================
# Node-PTY Service Dockerfile
# ==============================================================================
# Node.js 20-slim base with node-pty build dependencies and Git.
# Exposes WebSocket + HTTP API on PORT (default: 8000).
#
# Build:
#   docker build -t node-pty-service .
#
# Run (standalone):
#   docker run -p 8000:8000 node-pty-service
# ==============================================================================

FROM node:20-slim

# Install system dependencies for node-pty compilation and Git operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package files first for layer caching
COPY package.json package-lock.json* ./

# Install production dependencies (node-pty requires native compilation)
RUN npm install --omit=dev

# Copy application source
COPY src/ ./src/
COPY config/ ./config/

# Create artifacts directory (mount point for persistent file system)
RUN mkdir -p /app/artifacts

# Expose WebSocket + HTTP API port
EXPOSE 8000

# Health check via HTTP /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["node", "src/server.js"]
