#!/bin/bash
set -e

CLAUDE_HOME="${CLAUDE_HOME:-/app/artifacts}"
export HOME="$CLAUDE_HOME"

# Verificar se Claude Code já está instalado
if ! command -v claude &> /dev/null; then
    echo "[entrypoint] Claude Code not found. Checking connectivity..."

    # Verificação de rede antes do download (evita crash loop silencioso)
    if ! curl -s --max-time 10 https://registry.npmjs.org > /dev/null 2>&1; then
        # Diagnóstico: HTTP funciona mas HTTPS não = CA certs faltando
        if curl -s --max-time 10 http://registry.npmjs.org > /dev/null 2>&1; then
            echo "[entrypoint] ERROR: HTTPS fails but HTTP works — missing CA certificates."
            echo "[entrypoint] Run: apt-get install -y ca-certificates && update-ca-certificates"
        else
            echo "[entrypoint] ERROR: No internet connection detected."
            echo "[entrypoint] Cannot download Claude Code without network access."
            echo "[entrypoint] Ensure the container has internet access and try again."
        fi
        exit 1
    fi

    echo "[entrypoint] Network OK. Downloading Claude Code CLI..."
    npm install -g @anthropic-ai/claude-code

    echo "[entrypoint] Claude Code installed successfully."
else
    echo "[entrypoint] Claude Code already installed (cached)."
fi

# Verificar se ANTHROPIC_API_KEY está configurada (warning, não bloqueia)
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "[entrypoint] WARNING: ANTHROPIC_API_KEY is not set."
    echo "[entrypoint] Claude Code will not work without a valid API key."
fi

# Iniciar servidor WebSocket
echo "[entrypoint] Starting Claude Code WebSocket server..."
exec node src/server.js
