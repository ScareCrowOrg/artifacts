# Ollama Service

Canonical artifact for the Ollama LLM inference service, providing a containerized Ollama instance with ScareVerse heartbeat integration.

## Purpose

This directory contains the canonical definition for the Ollama service in the ScareVerse infrastructure:
- **LLM inference**: Runs Ollama to serve large language models locally
- **Heartbeat integration**: Registers service availability in Redis L1 via `heartbeat.py`
- **ScareVerse compatibility**: Follows the canonical service manifest pattern for deployment

## Directory Structure

```
ollama/
├── main.py              - Service entry point (may delegate to Ollama binary)
├── heartbeat.py         - Redis L1 heartbeat registration for service discovery
├── entrypoint-raw.sh    - Container entrypoint script for Ollama startup
├── Dockerfile           - Container image definition extending Ollama base
├── docker-compose.yml   - Local development compose configuration
└── manifest.json        - Artifact manifest with image tag and checksum
```

## How to Use

```bash
# Run via Docker Compose
docker-compose up ollama

# Pull and run a model (once the service is up)
curl http://localhost:11434/api/generate -d '{
  "model": "llama2",
  "prompt": "Hello, world!"
}'
```

### Service Discovery

The service registers itself in Redis L1 under the heartbeat key pattern so GateKeeper can discover and route LLM jobs to it automatically.

### Manifest

The `manifest.json` file tracks the current built image tag and SHA256 checksum used by the deployment pipeline.

## Content Index

| File | Description |
|---|---|
| `main.py` | Service initialization and startup logic |
| `heartbeat.py` | Redis L1 heartbeat for service discovery |
| `entrypoint-raw.sh` | Raw container entrypoint for Ollama binary |
| `Dockerfile` | Container image extending Ollama base image |
| `docker-compose.yml` | Local compose configuration |
| `manifest.json` | Deployment manifest (image tag, checksum) |
