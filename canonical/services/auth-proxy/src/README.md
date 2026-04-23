# Auth Proxy Source

Rust source code for the Auth Proxy service — an Axum-based HTTP/WebSocket reverse proxy that validates session tokens before forwarding requests to Vite and Backend.

## Purpose

This directory contains the core implementation of the Auth Proxy service:
- **Session validation**: Every `/artifacts/*` request is checked against the Backend session endpoint
- **Transparent proxying**: Validated HTTP requests are streamed to Vite upstream
- **WebSocket proxying**: WebSocket connections are upgraded and proxied transparently
- **Redis heartbeat**: Service registers readiness in Redis L1 so Traefik can route traffic
- **Graceful shutdown**: Handles SIGTERM/SIGINT with a 30-second grace period

## Directory Structure

```
src/
├── main.rs      - Entry point; initializes Axum server, shared state, and routing
├── config.rs    - Configuration struct loaded from environment variables
├── proxy.rs     - HTTP reverse proxy handler with session validation
└── ws_proxy.rs  - WebSocket upgrade and proxy handler
```

## How to Use

The source is compiled as part of the `auth-proxy` Rust service:

```bash
# Build from the auth-proxy root
cd artifacts/canonical/services/auth-proxy
cargo build --release

# Or via Docker
docker build -t auth-proxy .
```

### Key Environment Variables

| Variable | Description |
|---|---|
| `VITE_UPSTREAM` | Vite upstream URL (e.g., `http://vite:5052`) |
| `BACKEND_AUTH_URL` | Backend session-check endpoint |
| `BACKEND_UPSTREAM` | Backend base URL (e.g., `http://backend:5050`) |
| `REDIS_URL` | Redis L1 URL for heartbeat registration |
| `PORT` | Listening port (default: `8080`) |

## Content Index

| File | Description |
|---|---|
| `main.rs` | Application entry point; Axum server setup and graceful shutdown |
| `config.rs` | Environment-based configuration struct |
| `proxy.rs` | HTTP proxy handler with session validation logic |
| `ws_proxy.rs` | WebSocket proxy handler for real-time connections |
