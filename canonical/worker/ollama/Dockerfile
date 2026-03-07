# Ollama Worker – Combined Service + HTTP API
# Extends official Ollama image with Python worker for GateKeeper integration

FROM ollama/ollama:latest

WORKDIR /app

# Install Python + dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker files
COPY config.py main.py ./

# Expose both ports
# 11434: Ollama API
# 8080: Worker HTTP API
EXPOSE 11434 8080

# Health check for worker endpoint
HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=5 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run both services: Ollama in background, worker in foreground
CMD ollama serve & sleep 10 && python main.py
