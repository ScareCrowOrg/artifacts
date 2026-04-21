# ==============================================================================
# Ollama Service with Model Pre-loading and Heartbeat
# ==============================================================================
# Extends official Ollama image with:
# 1. entrypoint-raw.sh: pre-pulls models, starts heartbeat, runs Ollama
# 2. heartbeat.py: registers state:service:ollama:available in Redis L1
#

FROM ollama/ollama:latest

# Install curl + python3 (for heartbeat)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for heartbeat
RUN pip3 install --no-cache-dir --break-system-packages redis httpx

# Copy heartbeat script and entrypoint
COPY heartbeat.py /app/heartbeat.py
COPY entrypoint-raw.sh /entrypoint.sh

RUN chmod +x /app/heartbeat.py /entrypoint.sh

# Set Python path for imports (artifacts mounted via docker-compose volume)
ENV PYTHONPATH=/app/artifacts

# Override the default CMD with our entrypoint
ENTRYPOINT ["/entrypoint.sh"]
