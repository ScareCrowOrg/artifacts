FROM python:3.11-slim

WORKDIR /app/gatekeeper

# Install system dependencies (needed for subprocess venv creation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy GateKeeper source code
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# PYTHONPATH allows importing from artifacts/canonical/shared/ and canonical/
# Volume mount provides: /app/artifacts/canonical/ (workers, shared, job-types)
ENV PYTHONPATH=/app/artifacts

# Workers path inside the container (populated via volume mount)
ENV WORKERS_PATH=/app/artifacts/canonical/workers

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
