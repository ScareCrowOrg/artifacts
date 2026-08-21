FROM nvidia/cuda:12.6.3-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Dependências de sistema: compiladores + libs para visão/gráficos
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    ninja-build \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python 3.11 como padrão (ensurepip é desabilitado no Ubuntu, usamos get-pip.py)
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 \
    && python3.11 -m pip install --upgrade pip setuptools wheel

# PyTorch com CUDA 12.6 explícito (--index-url cu126)
# ComfyUI main passou a depender de comfy-kitchen, que exige torch >= 2.7.0:
# torch.library.infer_schema só aceita builtin generics (PEP 585) a partir do 2.7
# e torch.float8_e8m0fnu (usado em comfy_kitchen) também só existe no 2.7+.
# Com torch 2.5.1 o import de comfy_kitchen crasha com ValueError.
# Versões fixadas para evitar backtracking silencioso em caso de DNS flaky.
# --retries 5: tolera falhas DNS intermitentes do download.pytorch.org
RUN python3.11 -m pip install --no-cache-dir --retries 5 --timeout 120 \
    "torch==2.7.1+cu126" "torchvision==0.22.1+cu126" "torchaudio==2.7.1+cu126" \
    --index-url https://download.pytorch.org/whl/cu126

WORKDIR /app

# ComfyUI Core (shallow clone para evitar rate limiting)
RUN GIT_TERMINAL_PROMPT=0 git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /app/comfyui \
    && cd /app/comfyui \
    && python3.11 -m pip install --no-cache-dir -r requirements.txt sqlalchemy aiofiles

# Custom Nodes (ordem importa: Manager -> 3D)
# Nota: ComfyUI-HunyuanImageWrapper foi removido do GitHub do Kijai.
# Alternativas: Tencent HunyuanImage-2.1 (oficial) ou EricRollei/Comfy_HunyuanImage3
WORKDIR /app/comfyui/custom_nodes

RUN GIT_TERMINAL_PROMPT=0 git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Manager.git

# kornia<0.7.4: 0.8.3 SEGFAULTa com torch.jit.script no import (essential.py:90) —
#   confirmado em runtime também com torch 2.7.1+cu126 (não só no 2.5.1).
#   ComfyUI requirements pede kornia>=0.7.1 → 0.7.3 satisfaz e importa limpo.
# numpy<2 REMOVIDO: torch 2.7+ é compilado com numpy 2.x ABI — pinar numpy<2 causaria
#   o erro inverso "Failed to initialize NumPy: _ARRAY_API not found".
# setuptools<75: build_ext do Hunyuan3DWrapper (custom_rasterizer) roda via setup.py.
RUN python3.11 -m pip install --no-cache-dir "kornia<0.7.4" "setuptools<75"

# Hunyuan3DWrapper v2 (FP8) — compila extensões C++ com nvcc (devel necessário)
# TORCH_CUDA_ARCH_LIST explícito: docker build não tem GPU visível para auto-detecção
ENV TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9"
RUN GIT_TERMINAL_PROMPT=0 git clone --depth 1 https://github.com/Kijai/ComfyUI-Hunyuan3DWrapper.git \
    && cd ComfyUI-Hunyuan3DWrapper \
    && python3.11 -m pip install --no-cache-dir -r requirements.txt \
    && cd hy3dgen/texgen/custom_rasterizer \
    && python3.11 setup.py build_ext --inplace \
    && cd /app/comfyui/custom_nodes/ComfyUI-Hunyuan3DWrapper/hy3dgen/texgen/differentiable_renderer \
    && python3.11 setup.py build_ext --inplace

# Patch: safetensors from_single_file fix
# Kijai's pipelines.py uses load_torch_file() which returns flat keys
# for safetensors (model.dit.blocks.0.weight), but code expects nested
# dict (ckpt["model"] = {...}). Add prefix-splitting logic.
RUN python3.11 <<'PYEOF'
f = '/app/comfyui/custom_nodes/ComfyUI-Hunyuan3DWrapper/hy3dshape/hy3dshape/pipelines.py'
c = open(f).read()
old = 'ckpt = load_torch_file(ckpt_path)'
new = '''ckpt = load_torch_file(ckpt_path)
        if "model" not in ckpt:
            split_ckpt = {}
            for key, value in ckpt.items():
                prefix = key.split('.')[0]
                inner_key = '.'.join(key.split('.')[1:])
                if prefix not in split_ckpt:
                    split_ckpt[prefix] = {}
                split_ckpt[prefix][inner_key] = value
            ckpt = split_ckpt'''
assert old in c, 'Anchor not found in pipelines.py'
c = c.replace(old, new, 1)
open(f, 'w').write(c)
print('PATCH APPLIED: safetensors prefix split')
PYEOF

# omegaconf + rembg — missing transitive dependencies for Hy3D shape model
# Kijai's requirements.txt doesn't include them, but runtime lazy-imports them
# rembg[cpu] includes onnxruntime backend
# Pin coverage>=7.0: rembg → pymatting → numba → coverage.types.Tracer
# coverage 6.x removed coverage.types; only 7.x+ has the types.py module.
# Also: /app/artifacts/coverage/ (from repo) shadows pip package — keep tenant clean.
RUN python3.11 -m pip install --no-cache-dir omegaconf "rembg[cpu]" timm "coverage>=7.0"

# ScareVerse Wrapper (FastAPI + BaseService heartbeat)
WORKDIR /app
COPY wrapper/requirements.txt /app/wrapper/requirements.txt
RUN python3.11 -m pip install --no-cache-dir -r /app/wrapper/requirements.txt

COPY wrapper/ /app/wrapper/
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8188 9090
ENTRYPOINT ["/app/entrypoint.sh"]
