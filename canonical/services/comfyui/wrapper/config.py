import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
WRAPPER_PORT = int(os.getenv("WRAPPER_PORT", "9090"))
COMFYUI_PORT = int(os.getenv("COMFYUI_PORT", "8188"))
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "127.0.0.1")

REDIS_L1_HOST = os.getenv("REDIS_L1_HOST", "redis")
REDIS_L1_PORT = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_PASSWORD = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "60"))
HEARTBEAT_TTL = int(os.getenv("HEARTBEAT_TTL", "180"))
