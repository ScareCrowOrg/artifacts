# Stable Diffusion Worker – Combined Service + HTTP API
# Extends Stable Diffusion GPU service with Python worker for GateKeeper integration

FROM pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime

WORKDIR /app

# Install base dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Stable Diffusion dependencies
# Pin huggingface-hub to compatible version (0.24.x has cached_download, newer versions removed it)
RUN pip install --no-cache-dir \
    "huggingface-hub>=0.20.0,<0.25.0" \
    diffusers==0.26.3 \
    transformers==4.37.2 \
    accelerate==0.27.2 \
    safetensors==0.4.2 \
    opencv-python-headless \
    fastapi==0.110.3 \
    uvicorn[standard]==0.29.0

# Fix NumPy 2 compatibility with PyTorch 2.2.1
RUN pip install --no-cache-dir --force-reinstall "numpy==1.26.3"

# Copy SD API service
COPY sd_api.py ./sd_api.py
COPY test_gpu.py ./test_gpu.py

# Copy worker files
COPY config.py main.py ./

# Install worker dependencies (--break-system-packages for PEP 668 compliance)
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Expose both ports
# 9090: Stable Diffusion API
# 8080: Worker HTTP API
EXPOSE 9090 8080

# Health check for worker endpoint
HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=5 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run both services: SD API in background, worker in foreground
CMD python sd_api.py & sleep 10 && python main.py
