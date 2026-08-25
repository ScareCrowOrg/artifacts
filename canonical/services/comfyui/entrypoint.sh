#!/bin/bash
# ==============================================================================
# ScareVerse ComfyUI Service Entrypoint
# Orquestra ComfyUI (background) + ScareVerse Wrapper FastAPI (background, PID 1)
#
# Fases:
#   Fase 0: Early Heartbeat (desacoplado do FastAPI)
#   Fase 1: Model Download com self-healing (valida integridade, re-download se corrompido)
#   Fase 1.5: Hunyuan3D Model Download com self-healing
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

# ── Helpers: Self-Healing de modelos (validação + download) ────────────────────
# Valida se um arquivo é um safetensors íntegro (lê só o header, rápido).
# Retorna 0 se válido; 1 se ausente/corrompido/incompleto.
# Pegga ex.: "Error while deserializing header: incomplete metadata, file not
# fully covered" (download truncado) e "Failed to determine the start of the
# metadata" (arquivo corrompido).
is_valid_safetensors() {
    python -c "from safetensors import safe_open; safe_open('$1', framework='pt')" >/dev/null 2>&1
}

# Baixa um modelo com self-healing: resume (-C -), retry em erro transiente,
# validação pós-download e re-tentativa.
#  - Se curl falhar (rede) → mantém o parcial p/ resume na próxima tentativa.
#  - Se curl completar mas o arquivo for inválido → remove o corrompido e baixa do zero.
#  - Após max_attempts, avisa e retorna 1 (serviço sobe; geração 502 até modelo OK).
self_heal_download() {
    local target="$1" url="$2" max_attempts="${3:-3}" attempt curl_ok
    for ((attempt=1; attempt<=max_attempts; attempt++)); do
        if [ -n "${HUGGINGFACE_TOKEN}" ]; then
            curl -f -L -C - --retry 3 --retry-all-errors --connect-timeout 20 \
                -H "Authorization: Bearer ${HUGGINGFACE_TOKEN}" -o "${target}" "${url}" 2>/dev/null
        else
            curl -f -L -C - --retry 3 --retry-all-errors --connect-timeout 20 \
                -o "${target}" "${url}" 2>/dev/null
        fi
        curl_ok=$?
        if is_valid_safetensors "${target}"; then
            echo "[entrypoint] Modelo validado OK: ${target}"
            return 0
        fi
        if [ "$curl_ok" -eq 0 ]; then
            echo "[entrypoint] Tentativa ${attempt}/${max_attempts}: download completo mas arquivo inválido (${target}). Removendo corrompido e baixando do zero..."
            rm -f "${target}"
        else
            echo "[entrypoint] Tentativa ${attempt}/${max_attempts}: conexão falhou (${target}). Re-tentando resume..."
        fi
        sleep 5
    done
    echo "[entrypoint] AVISO: download/validação falhou após ${max_attempts} tentativas: ${target}. Geração retornará 502 até o modelo estar OK."
    return 1
}

# ── Fase 0: Early Heartbeat (one-shot, desacoplado do FastAPI) ─────────────────
# Registra o serviço em Redis L1 imediatamente (one-shot, TTL 300s), antes de
# qualquer operação de startup (download, ComfyUI, wrapper). O wrapper assume
# o heartbeat contínuo quando ficar pronto (Fase 4).
echo "[entrypoint] Fase 0: Iniciando heartbeat antecipado..."
python /app/artifacts/canonical/services/comfyui/heartbeat.py &
EARLY_HB_PID=$!
echo "[entrypoint] Early heartbeat iniciado (PID: $EARLY_HB_PID)"

# ── Fase 1: Model Download com Self-Healing (cacheado no volume) ──────────────
MODEL_NAME="${SDXL_MODEL_NAME:-sd_xl_base_1.0.safetensors}"
MODEL_CHECKPOINT_DIR="/app/comfyui/models/checkpoints"
MODEL_PATH="${MODEL_CHECKPOINT_DIR}/${MODEL_NAME}"
MODEL_URL="https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/${MODEL_NAME}"

echo "[entrypoint] Fase 1: Verificando modelo '${MODEL_NAME}' (self-healing)..."
if [ -f "$MODEL_PATH" ] && is_valid_safetensors "$MODEL_PATH"; then
    echo "[entrypoint] Fase 1: Modelo '${MODEL_NAME}' íntegro, download ignorado."
else
    if [ -f "$MODEL_PATH" ]; then
        echo "[entrypoint] Fase 1: Modelo '${MODEL_NAME}' corrompido/incompleto. Auto-reparando..."
    else
        echo "[entrypoint] Fase 1: Modelo '${MODEL_NAME}' não encontrado. Iniciando download..."
    fi
    self_heal_download "$MODEL_PATH" "$MODEL_URL"
fi

# ── Fase 1.5: Download Hunyuan3D com Self-Healing (cacheado no volume) ────────
# Modelo Hunyuan3D v2 FP8 para geração 3D via Hy3D nodes (Kijai ComfyUI-Hunyuan3DWrapper).
# O custom node Kijai já está instalado no Dockerfile.
# O modelo fica cacheado no volume comfyui-models, em /app/comfyui/models/diffusion_models/
# (Hy3D_2_1SimpleMeshGen carrega modelos de diffusion_models/, não de hunyuan3d/)
HUNYUAN3D_MODEL_DIR="/app/comfyui/models/diffusion_models"
HUNYUAN3D_MODEL_NAME="${HUNYUAN3D_MODEL_NAME:-hunyuan_3d_v2.1.safetensors}"
HUNYUAN3D_MODEL_PATH="${HUNYUAN3D_MODEL_DIR}/${HUNYUAN3D_MODEL_NAME}"
HUNYUAN3D_MODEL_URL="${HUNYUAN3D_MODEL_URL:-https://huggingface.co/Comfy-Org/hunyuan3D_2.1_repackaged/resolve/main/${HUNYUAN3D_MODEL_NAME}}"

echo "[entrypoint] Fase 1.5: Verificando modelo Hunyuan3D '${HUNYUAN3D_MODEL_NAME}' (self-healing)..."
mkdir -p "${HUNYUAN3D_MODEL_DIR}"
if [ -f "$HUNYUAN3D_MODEL_PATH" ] && is_valid_safetensors "$HUNYUAN3D_MODEL_PATH"; then
    echo "[entrypoint] Fase 1.5: Modelo Hunyuan3D '${HUNYUAN3D_MODEL_NAME}' íntegro, download ignorado."
else
    if [ -f "$HUNYUAN3D_MODEL_PATH" ]; then
        echo "[entrypoint] Fase 1.5: Modelo Hunyuan3D '${HUNYUAN3D_MODEL_NAME}' corrompido/incompleto. Auto-reparando..."
    else
        echo "[entrypoint] Fase 1.5: Modelo Hunyuan3D '${HUNYUAN3D_MODEL_NAME}' não encontrado. Iniciando download..."
    fi
    self_heal_download "$HUNYUAN3D_MODEL_PATH" "$HUNYUAN3D_MODEL_URL"
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
