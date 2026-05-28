FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

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

# PyTorch com CUDA 12.1 explícito (--index-url cu121)
RUN python3.11 -m pip install --no-cache-dir torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu121

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

# Pin kornia < 0.7.4: 0.8.3 crasha com torch.jit.script em PyTorch 2.5.1+cu121
# (segfault em kornia/geometry/epipolar/essential.py durante import)
RUN python3.11 -m pip install --no-cache-dir "kornia<0.7.4"

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

# ScareVerse Wrapper (FastAPI + BaseService heartbeat)
WORKDIR /app
COPY wrapper/requirements.txt /app/wrapper/requirements.txt
RUN python3.11 -m pip install --no-cache-dir -r /app/wrapper/requirements.txt

COPY wrapper/ /app/wrapper/
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8188 9090
ENTRYPOINT ["/app/entrypoint.sh"]
