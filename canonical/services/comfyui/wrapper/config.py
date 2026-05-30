import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
WRAPPER_PORT = int(os.getenv("WRAPPER_PORT", "9090"))
COMFYUI_PORT = int(os.getenv("COMFYUI_PORT", "8188"))
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "127.0.0.1")

# Poll & timeout for POST /generate
COMFYUI_POLL_INTERVAL = float(os.getenv("COMFYUI_POLL_INTERVAL", "1.0"))
COMFYUI_GENERATE_TIMEOUT = int(os.getenv("COMFYUI_GENERATE_TIMEOUT", "120"))

# Removido — Redis config agora gerenciado pelo BaseService
# (lê diretamente de env vars com defaults próprios)
