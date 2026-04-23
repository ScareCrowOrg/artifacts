# GateKeeper Service

Unified job dispatcher service that routes AI workloads to appropriate worker backends using a dual-Redis architecture.

## Purpose

GateKeeper is a JOB CONSUMER (not a health checker) responsible for:
- Connecting to Redis L1 (ScareRunner/owner) and Redis L2 (CentralHub/global)
- Consuming jobs via BRPOP (L1 priority, L2 fallback)
- Routing jobs to the correct execution model: HTTP service or subprocess worker
- Persisting job results and errors back to Redis
- Orchestrating resource scaling decisions based on host telemetry

GateKeeper supports two execution models:
- **`service`**: Routes job via HTTP POST to a long-lived worker service
- **`subprocess`**: Spawns an isolated Python subprocess for ephemeral workers

## Directory Structure

```
gatekeeper/
├── main.py               - Entry point; connects Redis, runs BRPOP dispatch loop
├── config.py             - Centralized config via config_manager (Redis L1 → env fallback)
├── orchestrator.py       - Resource orchestrator; reads host telemetry, publishes scale commands
├── job_executor.py       - Subprocess execution model handler
├── service_executor.py   - HTTP service execution model handler
├── worker_discovery.py   - Discovers available workers from Redis registry
├── pooling.py            - Multi-source pooling strategy for job queues
├── heartbeat.py          - Fire-and-forget heartbeat registration to Redis L1
├── venv_manager.py       - Virtual environment management for subprocess workers
├── metrics.py            - Service metrics collection and reporting
├── json_logger.py        - Structured JSON logging utility
├── conftest.py           - Shared pytest fixtures
├── pytest.ini            - Pytest configuration
├── requirements.txt      - Python dependencies
├── Dockerfile            - Container image definition
├── docker-compose.yml    - Local development compose configuration
├── entrypoint.sh         - Container entrypoint script
├── manifest.json         - Artifact manifest with image tag and checksum
└── tests/                - Unit and integration tests
```

## How to Use

### Running Locally

```bash
# Using Docker Compose
docker-compose up gatekeeper

# Direct Python execution (requires Redis)
pip install -r requirements.txt
python main.py
```

### Environment Variables

Key configuration is resolved via Redis L1 config keys with environment variable fallback:
- `REDIS_L1_URL` - Redis L1 (owner node) connection URL
- `REDIS_L2_URL` - Redis L2 (CentralHub/global) connection URL
- `LOG_LEVEL` - Logging level (default: `INFO`)

### Job Payload Format

Jobs are JSON objects consumed from Redis queues:
```json
{
  "job_id": "uuid",
  "job_type": "stable-diffusion",
  "execution_model": "service",
  "payload": {}
}
```

## Content Index

| File/Directory | Description |
|---|---|
| `main.py` | Service entry point and BRPOP dispatch loop |
| `config.py` | Configuration management with Redis L1 and env fallback |
| `orchestrator.py` | Resource orchestration and scale decision engine |
| `job_executor.py` | Subprocess-based worker execution handler |
| `service_executor.py` | HTTP-based service execution handler |
| `worker_discovery.py` | Worker registry discovery from Redis |
| `pooling.py` | Multi-source job queue pooling strategy |
| `heartbeat.py` | Redis L1 heartbeat registration |
| `venv_manager.py` | Python virtual environment management |
| `metrics.py` | Service metrics collection |
| `tests/` | Unit and integration tests for all components |
