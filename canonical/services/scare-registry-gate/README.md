# ScareRegistryGate

**ScareRegistryGate** is a local OCI v2 registry gateway service for the ScareVerse platform. It accepts `docker push` and `docker pull` requests with Basic Auth, streams blob data to Cloudflare R2, and notifies CentralHub after each manifest push.

## Architecture

```
docker push ──► ScareRegistryGate (port 5678)
                  │
                  ├─ Blob PATCH/PUT ──► Cloudflare R2 (PutObject)
                  ├─ Manifest PUT  ──► Cloudflare R2 (PutObject)
                  │                    └─► CentralHub POST /api/registry/manifests
                  └─ Blob/Manifest GET ──► 307 redirect to R2 public URL

docker pull ──► ScareRegistryGate ──► 307 redirect to R2 public URL
```

## OCI v2 Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/v2/` | Version check / auth challenge |
| `POST` | `/v2/:registry/:planet/:name/blobs/uploads/` | Initiate blob upload |
| `PATCH`| `/v2/:registry/:planet/:name/blobs/uploads/:uuid` | Send blob chunk |
| `PUT`  | `/v2/:registry/:planet/:name/blobs/uploads/:uuid?digest=sha256:…` | Finalise blob upload |
| `HEAD` | `/v2/:registry/:planet/:name/blobs/:digest` | Check blob existence |
| `GET`  | `/v2/:registry/:planet/:name/blobs/:digest` | Redirect to R2 blob URL |
| `PUT`  | `/v2/:registry/:planet/:name/manifests/:reference` | Push manifest |
| `GET`  | `/v2/:registry/:planet/:name/manifests/:reference` | Redirect to R2 manifest URL |
| `GET`  | `/health` | Liveness probe |

## Image Namespace

Images use a **3-component namespace** matching the OCI path structure:

```
localhost:5678/{registry}/{planet}/{image-name}:{tag}
```

Example:
```sh
docker tag my-image:latest localhost:5678/scareverse/earth/my-image:latest
docker push localhost:5678/scareverse/earth/my-image:latest
```

## R2 Key Layout

```
blobs/{registry}/{planet}/{name}/sha256:{hex}      ← stored blob layers
manifests/{registry}/{planet}/{name}/{tag}          ← manifest by tag
manifests/{registry}/{planet}/{name}/sha256:{hex}  ← manifest by digest
uploads/{uuid}                                      ← temporary upload sessions (Redis only)
```

## Configuration

All settings are read from environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GATE_PORT` | `5678` | Listening port |
| `R2_ACCOUNT_ID` | *(required)* | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | *(required)* | R2 S3-compatible access key |
| `R2_SECRET_ACCESS_KEY` | *(required)* | R2 S3-compatible secret key |
| `R2_BUCKET` | `scareverse-registry` | R2 bucket name |
| `R2_PUBLIC_URL` | *(required for pulls)* | Public base URL, e.g. `https://pub-xxx.r2.dev` |
| `CENTRALHUB_URL` | *(required)* | CentralHub base URL |
| `CENTRALHUB_API_KEY` | *(required)* | Bearer token for CentralHub |
| `REGISTRY_USERNAME` | `scareverse` | Docker Basic Auth username |
| `REGISTRY_PASSWORD` | *(empty)* | Docker Basic Auth password |
| `REDIS_L1_HOST` | `redis-local` | Redis hostname |
| `REDIS_L1_PORT` | `6380` | Redis port |
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis password |
| `REDIS_L1_DB` | `0` | Redis database index |
| `HEARTBEAT_INTERVAL` | `20` | Heartbeat renewal interval (seconds) |
| `LOG_LEVEL` | `INFO` | Tracing filter (`DEBUG`, `INFO`, `WARN`, `ERROR`) |

## Blob Upload Flow (Option-B: In-Memory Buffer)

1. **POST** `/blobs/uploads/` → generates a UUID, stores session in Redis (TTL 3600s), returns `202 Accepted` with `Location` header.
2. **PATCH** `/blobs/uploads/{uuid}` → appends request body to an in-memory `DashMap` buffer for the session UUID.
3. **PUT** `/blobs/uploads/{uuid}?digest=sha256:…` → collects all buffered bytes, verifies the SHA-256 digest, calls R2 `PutObject`, then deletes the Redis session.

> **Note:** Large layers (200MB+) are held in RAM during the upload. No disk is used.

## Usage Example

```sh
# Configure Docker daemon to use an insecure local registry
# Add to /etc/docker/daemon.json:
# { "insecure-registries": ["localhost:5678"] }

# Authenticate
docker login localhost:5678 -u scareverse -p <password>

# Push an image
docker tag ubuntu:22.04 localhost:5678/scareverse/earth/ubuntu:22.04
docker push localhost:5678/scareverse/earth/ubuntu:22.04

# Pull an image (redirected to R2 public URL)
docker pull localhost:5678/scareverse/earth/ubuntu:22.04
```

## Local Development

```sh
# Build and run with docker-compose
docker-compose up --build

# Check health
curl http://localhost:5678/health

# OCI version check (will return 401 - correct behaviour)
curl -v http://localhost:5678/v2/
```

## Launcher Integration

The service is registered in `manifest.json`. The following vault secrets must be provisioned before launching:

- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `CENTRALHUB_URL`
- `CENTRALHUB_API_KEY`

The heartbeat key `state:service:scare-registry-gate:available` is maintained in Redis L1 by `heartbeat.py`, signalling to GateKeeper that the service is alive.
