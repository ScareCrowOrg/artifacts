#!/bin/sh
#
# Ollama service entrypoint (replaces original entrypoint.sh for raw container).
# 1. Pre-pulls models (from entrypoint-ollama.sh)
# 2. Starts heartbeat.py (fire-and-forget, registers in Redis and exits)
# 3. Runs Ollama in foreground (PID 1)
#

set -e

echo "[entrypoint] Starting Ollama service..."

# ============================================================================
# Start Ollama and wait for readiness
# ============================================================================

echo "[entrypoint] Starting Ollama server..."
/usr/bin/ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready (max 120s)
echo "[entrypoint] Waiting for Ollama to be ready..."
TIMEOUT=120
ELAPSED=0
while ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; do
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "[entrypoint] ERROR: Ollama failed to start within ${TIMEOUT}s"
    kill $OLLAMA_PID 2>/dev/null || true
    exit 1
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
  echo "[entrypoint] Still waiting... ($ELAPSED/${TIMEOUT}s)"
done

echo "[entrypoint] ✅ Ollama is ready!"

# ============================================================================
# Pre-pull models
# ============================================================================

echo "[entrypoint] Pre-pulling models..."

# Models from artifacts/canonical/ai_models/README.md
MODELS=(
  "mistral"           # 7B - general purpose
  "phi"               # 2.7B - fast, lightweight
  "phi3"              # 3.8B - Microsoft efficient
  "deepseek-coder"    # 6.7B - code generation
  "qwen2.5-coder"     # 14B - large code model
  "gemma"             # 7B - Google open model
)

for model in "${MODELS[@]}"; do
  echo "[entrypoint] Pulling $model..."
  if ollama pull "$model"; then
    echo "[entrypoint] ✅ $model pulled successfully"
  else
    echo "[entrypoint] ⚠️  Failed to pull $model (may retry on demand)"
  fi
done

echo "[entrypoint] ✅ Model initialization complete!"

# ============================================================================
# Start heartbeat in background (fire-and-forget)
# ============================================================================
# heartbeat.py will start asyncio task, register in Redis, and exit immediately

echo "[entrypoint] Starting Ollama heartbeat registration..."
python3 /app/heartbeat.py &

# Give heartbeat time to register
sleep 1

# ============================================================================
# Keep Ollama running in foreground (PID 1)
# ============================================================================

echo "[entrypoint] ✅ Ollama service ready"
wait $OLLAMA_PID
