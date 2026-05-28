#!/bin/bash
# ==============================================================================
# ScareVerse ComfyUI Service Entrypoint
# Orquestra ComfyUI (background) + ScareVerse Wrapper FastAPI (foreground, PID 1)
# ==============================================================================

COMFYUI_PID=0
WRAPPER_PID=0

_graceful_shutdown() {
    echo "[entrypoint] Sinais de encerramento recebidos (SIGTERM/SIGINT)!"

    if [ "$WRAPPER_PID" -ne 0 ]; then
        echo "[entrypoint] Enviando SIGTERM para o ScareVerse Wrapper (PID: $WRAPPER_PID)..."
        kill -TERM "$WRAPPER_PID" 2>/dev/null
    fi

    if [ "$COMFYUI_PID" -ne 0 ]; then
        echo "[entrypoint] Enviando SIGTERM para o ComfyUI (PID: $COMFYUI_PID)..."
        kill -TERM "$COMFYUI_PID" 2>/dev/null
    fi

    wait "$WRAPPER_PID" 2>/dev/null
    wait "$COMFYUI_PID" 2>/dev/null
    echo "[entrypoint] Todos os processos finalizaram. Saindo."
    exit 0
}

trap _graceful_shutdown SIGTERM SIGINT

echo "[entrypoint] Inicializando o ComfyUI..."
cd /app/comfyui
python main.py --listen 0.0.0.0 --port 8188 --disable-smart-memory &
COMFYUI_PID=$!
echo "[entrypoint] ComfyUI iniciado (PID: $COMFYUI_PID, porta: 8188)"

echo "[entrypoint] Aguardando prontidão do ComfyUI (/system)..."
MAX_ATTEMPTS=60
ATTEMPT=1
READY=0

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    if curl -sf http://127.0.0.1:8188/ > /dev/null 2>&1; then
        echo "[entrypoint] ComfyUI pronto!"
        READY=1
        break
    fi
    echo "[entrypoint] ComfyUI carregando... ($ATTEMPT/$MAX_ATTEMPTS)"
    sleep 3
    ATTEMPT=$((ATTEMPT + 1))
done

if [ $READY -eq 0 ]; then
    echo "[entrypoint] ERRO: ComfyUI não respondeu após $MAX_ATTEMPTS tentativas." >&2
    kill -KILL "$COMFYUI_PID" 2>/dev/null
    exit 1
fi

echo "[entrypoint] Inicializando ScareVerse Wrapper..."
cd /app/wrapper
python main.py &
WRAPPER_PID=$!
echo "[entrypoint] Wrapper iniciado (PID: $WRAPPER_PID)"

wait "$WRAPPER_PID" "$COMFYUI_PID"
