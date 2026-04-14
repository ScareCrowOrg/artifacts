# Traefik Service Worker

Reverse proxy for the ScareVerse platform. Replaces Nginx-Unit as the HTTP entry point.

## Overview

Traefik v3.1.0 auto-discovers services via Docker labels — no manual route registration is needed. Routes are defined on each service's `docker-compose.yml` as Traefik labels.

## Route Hierarchy

| Path | Service | Port | Priority |
|------|---------|------|----------|
| `/artifacts*` | auth-proxy | 5055 | 100 (highest) |
| `/api*` | backend | 5050 | 10 |
| `/*` | vite | 5052 | 1 (catch-all) |

## Ports

- **80**: HTTP reverse proxy (public)
- **8080**: Traefik dashboard / API (`http://localhost:8080/dashboard`)

## Heartbeat

Registers `state:service:traefik:available` in Redis L1 using the standard `BaseService` heartbeat pattern.

## Configuration

Static configuration lives in `traefik.yml`. Dynamic routing is fully label-driven.

## Tests

```bash
cd tests/
python3 -m pytest test_heartbeat.py -v
```
