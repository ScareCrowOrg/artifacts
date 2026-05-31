import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
WRAPPER_PORT = int(os.getenv("WRAPPER_PORT", "9090"))
COMFYUI_PORT = int(os.getenv("COMFYUI_PORT", "8188"))
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "127.0.0.1")

# Poll & timeout for POST /generate (SDXL 2D)
COMFYUI_POLL_INTERVAL = float(os.getenv("COMFYUI_POLL_INTERVAL", "1.0"))
COMFYUI_GENERATE_TIMEOUT = int(os.getenv("COMFYUI_GENERATE_TIMEOUT", "120"))

# Poll & timeout for POST /generate-3d (Hunyuan3D)
HUNYUAN3D_POLL_INTERVAL = float(os.getenv("HUNYUAN3D_POLL_INTERVAL", "2.0"))
HUNYUAN3D_GENERATE_TIMEOUT = int(os.getenv("HUNYUAN3D_GENERATE_TIMEOUT", "600"))
HUNYUAN3D_MODEL_NAME = os.getenv("HUNYUAN3D_MODEL_NAME", "hunyuan3d-dit-v2-0-fp16.safetensors")

# Removido — Redis config agora gerenciado pelo BaseService
# (lê diretamente de env vars com defaults próprios)
