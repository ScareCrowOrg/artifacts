#!/bin/bash
# Ollama entrypoint: Start Ollama and pull default models

set -e

# Models to pre-pull (from artifacts/canonical/ai_models/README.md)
# Local Ollama models: ~4-14GB each, ~40GB total
MODELS=(
  "mistral"           # 7B - general purpose
  "phi"               # 2.7B - fast, lightweight
  "phi3"              # 3.8B - Microsoft efficient
  "deepseek-coder"    # 6.7B - code generation
  "deepseek-coder:latest"  # Ensure latest tag
  "qwen2.5-coder"     # 14B - large code model
  "gemma"             # 7B - Google open model
)

echo "[Ollama] Starting Ollama server..."
/usr/bin/ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready (max 120s)
echo "[Ollama] Waiting for Ollama to be ready..."
TIMEOUT=120
ELAPSED=0
while ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; do
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "[Ollama] ERROR: Ollama failed to start within ${TIMEOUT}s"
    kill $OLLAMA_PID 2>/dev/null || true
    exit 1
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
  echo "[Ollama] Still waiting... ($ELAPSED/${TIMEOUT}s)"
done

echo "[Ollama] ✅ Ollama is ready!"

# Pull models (will use cache if already present in mounted volume)
echo "[Ollama] Pre-pulling models..."
for model in "${MODELS[@]}"; do
  echo "[Ollama] Pulling $model..."
  if ollama pull "$model"; then
    echo "[Ollama] ✅ $model pulled successfully"
  else
    echo "[Ollama] ⚠️  Failed to pull $model (may retry on demand)"
  fi
done

echo "[Ollama] ✅ Model initialization complete!"

# Keep Ollama running
wait $OLLAMA_PID
