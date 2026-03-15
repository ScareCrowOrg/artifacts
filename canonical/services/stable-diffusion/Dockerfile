FROM pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install core packages
# Pin huggingface-hub to compatible version (0.24.x has cached_download, newer versions removed it)
RUN pip install --no-cache-dir \
    "huggingface-hub>=0.20.0,<0.25.0" \
    diffusers==0.26.3 \
    transformers==4.37.2 \
    accelerate==0.27.2 \
    safetensors==0.4.2 \
    opencv-python-headless \
    fastapi==0.110.3 \
    uvicorn[standard]==0.29.0 \
    redis==5.0.1

# Fix NumPy 2 compatibility with PyTorch 2.2.1
# Force numpy 1.26.3 which is compatible with PyTorch 2.2.1
# This must be done AFTER diffusers to satisfy version constraints
RUN pip install --no-cache-dir --force-reinstall "numpy==1.26.3"

COPY sd_api.py /app/sd_api.py
COPY test_gpu.py /app/test_gpu.py

EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9090/health || exit 1

CMD ["python", "sd_api.py"]
