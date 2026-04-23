# Node-PTY Service Source

Core implementation of the Node-PTY Service — an Express/WebSocket server providing interactive terminal (PTY) sessions and Git operations via HTTP API.

## Purpose

This directory contains the main server logic for the Node-PTY Service:
- **PTY sessions**: Creates and manages interactive terminal sessions using `node-pty`
- **Git operations**: Exposes HTTP endpoints for Git status, log, and clone
- **WebSocket protocol**: Handles PTY I/O (input, resize, close) over WebSocket connections
- **Redis heartbeat**: Registers service availability in Redis L1 for service discovery

## Directory Structure

```
src/
├── server.js      - Main entry point; Express server, WebSocket server, and routing
├── ptyManager.js  - PTY session lifecycle management (create, input, resize, close)
└── gitHelper.js   - Git operation implementations (status, log, clone)
```

## How to Use

The source is loaded by the service container entrypoint:

```bash
# Start the service
node src/server.js

# Or via Docker Compose from the service root
docker-compose up node-pty-service
```

### HTTP Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/git/status` | Get Git repository status |
| `POST` | `/api/git/log` | Get Git commit log |
| `POST` | `/api/git/clone` | Clone a Git repository |

### WebSocket Protocol

Connect to `ws://<host>:<port>/ws` and send JSON messages:

```json
{ "type": "input", "data": "ls -la\n" }
{ "type": "resize", "cols": 120, "rows": 40 }
{ "type": "close" }
```

## Content Index

| File | Description |
|---|---|
| `server.js` | Express HTTP + WebSocket server entry point |
| `ptyManager.js` | PTY session creation, I/O handling, and lifecycle management |
| `gitHelper.js` | Git operation implementations using child_process |
