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
# Versões fixadas para evitar backtracking silencioso em caso de DNS flaky.
# --retries 5: tolera falhas DNS intermitentes do download.pytorch.org
RUN python3.11 -m pip install --no-cache-dir --retries 5 --timeout 120 \
    "torch==2.5.1+cu121" "torchvision==0.20.1+cu121" "torchaudio==2.5.1+cu121" \
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
# Pin numpy<2: torch instalado acima foi compilado com numpy 1.x ABI,
# numpy 2.x causa "Failed to initialize NumPy: _ARRAY_API not found"
RUN python3.11 -m pip install --no-cache-dir "kornia<0.7.4" "numpy<2" "setuptools<75"

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
# Pin coverage<7.0: rembg → pymatting → numba → coverage.types.Tracer
# coverage 7.x removed coverage.types, breaking numba 0.59.x (Python 3.11)
RUN python3.11 -m pip install --no-cache-dir omegaconf "rembg[cpu]" timm "coverage<7.0"

# ScareVerse Wrapper (FastAPI + BaseService heartbeat)
WORKDIR /app
COPY wrapper/requirements.txt /app/wrapper/requirements.txt
RUN python3.11 -m pip install --no-cache-dir -r /app/wrapper/requirements.txt

COPY wrapper/ /app/wrapper/
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8188 9090
ENTRYPOINT ["/app/entrypoint.sh"]
