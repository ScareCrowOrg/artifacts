# ==============================================================================
# planet-beacon Service
# ==============================================================================
# Lightweight Python service that:
#   1. Scans artifacts/canonical/viewers/ for available viewers
#   2. Sends presence heartbeats to CentralHub every 60s (L2)
#   3. Registers a Redis L1 availability key via BaseService (L1)
# ==============================================================================

FROM python:3.11-slim

WORKDIR /app

# ── Python dependencies ────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Service code ───────────────────────────────────────────────────────────────
COPY config.py .
COPY viewer_scanner.py .
COPY presence_client.py .
COPY main.py .

# ── Log directory ──────────────────────────────────────────────────────────────
RUN mkdir -p /app/logs

# artifacts volume is mounted at runtime: /app/artifacts
# This provides access to canonical/shared/services/base_service.py (L1 heartbeat)
# and canonical/viewers/ (viewer scan target).

CMD ["python", "main.py"]
