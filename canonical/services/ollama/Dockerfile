# ==============================================================================
# Ollama FastAPI Wrapper Service
# ==============================================================================
# HTTP proxy to raw Ollama container with Redis L1 heartbeat registration.
#

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    httpx==0.25.1 \
    pydantic==2.4.2 \
    redis==5.0.1

# Copy service code
COPY main.py .

# Expose port
EXPOSE 11434

# Health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=30s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:11434/health', timeout=5).raise_for_status()" || exit 1

# Run service
CMD ["python", "main.py"]
