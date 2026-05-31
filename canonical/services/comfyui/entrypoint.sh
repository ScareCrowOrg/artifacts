#!/bin/bash
# ==============================================================================
# ScareVerse ComfyUI Service Entrypoint
# Orquestra ComfyUI (background) + ScareVerse Wrapper FastAPI (background, PID 1)
#
# Fases:
#   Fase 0: Early Heartbeat (desacoplado do FastAPI)
#   Fase 1: Model Download (cacheado no volume)
#   Fase 2: Start ComfyUI
#   Fase 3: Wait for ComfyUI ready
#   Fase 4: Start Wrapper
#   Fase 5: Wait for all processes
# ==============================================================================

COMFYUI_PID=0
WRAPPER_PID=0
EARLY_HB_PID=0

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

    if [ "$EARLY_HB_PID" -ne 0 ]; then
        echo "[entrypoint] Enviando SIGTERM para o Early Heartbeat (PID: $EARLY_HB_PID)..."
        kill -TERM "$EARLY_HB_PID" 2>/dev/null
    fi

    wait "$WRAPPER_PID" 2>/dev/null
    wait "$COMFYUI_PID" 2>/dev/null
    wait "$EARLY_HB_PID" 2>/dev/null
    echo "[entrypoint] Todos os processos finalizaram. Saindo."
    exit 0
}

trap _graceful_shutdown SIGTERM SIGINT

# ── Fase 0: Early Heartbeat (one-shot, desacoplado do FastAPI) ─────────────────
# Registra o serviço em Redis L1 imediatamente (one-shot, TTL 300s), antes de
# qualquer operação de startup (download, ComfyUI, wrapper). O wrapper assume
# o heartbeat contínuo quando ficar pronto (Fase 4).
echo "[entrypoint] Fase 0: Iniciando heartbeat antecipado..."
python /app/artifacts/canonical/services/comfyui/heartbeat.py &
EARLY_HB_PID=$!
echo "[entrypoint] Early heartbeat iniciado (PID: $EARLY_HB_PID)"

# ── Fase 1: Model Download (cacheado no volume) ───────────────────────────────
MODEL_NAME="${SDXL_MODEL_NAME:-sd_xl_base_1.0.safetensors}"
MODEL_CHECKPOINT_DIR="/app/comfyui/models/checkpoints"
MODEL_PATH="${MODEL_CHECKPOINT_DIR}/${MODEL_NAME}"

if [ ! -f "$MODEL_PATH" ]; then
    echo "[entrypoint] Fase 1: Modelo '${MODEL_NAME}' não encontrado. Iniciando download..."
    MODEL_URL="https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/${MODEL_NAME}"

    if [ -n "${HUGGINGFACE_TOKEN}" ]; then
        AUTH_HEADER="Authorization: Bearer ${HUGGINGFACE_TOKEN}"
        curl -f -L -H "${AUTH_HEADER}" -o "${MODEL_PATH}" "${MODEL_URL}"
    else
        curl -f -L -o "${MODEL_PATH}" "${MODEL_URL}"
    fi

    if [ $? -eq 0 ]; then
        echo "[entrypoint] Modelo baixado com sucesso (cacheado no volume 'comfyui-models')."
    else
        echo "[entrypoint] AVISO: Falha no download do modelo. POST /generate retornará 502 até o modelo estar disponível."
    fi
else
    echo "[entrypoint] Fase 1: Modelo '${MODEL_NAME}' encontrado no volume, download ignorado."
fi

# ── Fase 1.5: Download Hunyuan3D models (cacheado no volume) ───────────────────
# Modelo Hunyuan3D v2 FP8 para geração 3D via Hy3D nodes (Kijai ComfyUI-Hunyuan3DWrapper).
# O custom node Kijai já está instalado no Dockerfile.
# O modelo fica cacheado no volume comfyui-models, em /app/comfyui/models/diffusion_models/
# (Hy3D_2_1SimpleMeshGen carrega modelos de diffusion_models/, não de hunyuan3d/)
HUNYUAN3D_MODEL_DIR="/app/comfyui/models/diffusion_models"
HUNYUAN3D_MODEL_NAME="${HUNYUAN3D_MODEL_NAME:-hunyuan3d-dit-v2-0-fp16.safetensors}"
HUNYUAN3D_MODEL_PATH="${HUNYUAN3D_MODEL_DIR}/${HUNYUAN3D_MODEL_NAME}"
if [ ! -f "$HUNYUAN3D_MODEL_PATH" ]; then
    echo "[entrypoint] Fase 1.5: Modelo Hunyuan3D '${HUNYUAN3D_MODEL_NAME}' não encontrado. Iniciando download..."
    mkdir -p "${HUNYUAN3D_MODEL_DIR}"
    HUNYUAN3D_MODEL_URL="${HUNYUAN3D_MODEL_URL:-https://huggingface.co/Kijai/Hunyuan3D-2_safetensors/resolve/main/${HUNYUAN3D_MODEL_NAME}}"
    curl -f -L -o "${HUNYUAN3D_MODEL_PATH}" "${HUNYUAN3D_MODEL_URL}"
    if [ $? -eq 0 ]; then
        echo "[entrypoint] Modelo Hunyuan3D baixado com sucesso: ${HUNYUAN3D_MODEL_PATH}"
    else
        echo "[entrypoint] AVISO: Falha no download do modelo Hunyuan3D. POST /generate-3d retornará 502 até o modelo estar disponível."
    fi
else
    echo "[entrypoint] Fase 1.5: Modelo Hunyuan3D '${HUNYUAN3D_MODEL_NAME}' encontrado no volume, download ignorado."
fi

# ── Fase 2: Start ComfyUI (mantido do atual) ──────────────────────────────────
echo "[entrypoint] Fase 2: Inicializando o ComfyUI..."
cd /app/comfyui
python main.py --listen 0.0.0.0 --port 8188 --disable-smart-memory &
COMFYUI_PID=$!
echo "[entrypoint] ComfyUI iniciado (PID: $COMFYUI_PID, porta: 8188)"

# ── Fase 3: Wait for ComfyUI ready (mantido do atual) ─────────────────────────
echo "[entrypoint] Fase 3: Aguardando prontidão do ComfyUI (/system)..."
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

# ── Fase 4: Start Wrapper (mantido do atual) ──────────────────────────────────
echo "[entrypoint] Fase 4: Inicializando ScareVerse Wrapper..."
cd /app
python -m wrapper.main &
WRAPPER_PID=$!
echo "[entrypoint] Wrapper iniciado (PID: $WRAPPER_PID)"
# NOTA: O heartbeat do wrapper (BaseService no startup_event) também roda.
# Ambos escrevem na mesma chave Redis → idempotente. O heartbeat do wrapper
# assume quando o wrapper fica pronto (port_opened: true).

# ── Fase 5: Wait for all processes ────────────────────────────────────────────
echo "[entrypoint] Fase 5: Monitorando processos..."
wait "$COMFYUI_PID" "$WRAPPER_PID" "$EARLY_HB_PID"
