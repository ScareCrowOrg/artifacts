# Node-PTY Service

Persistent terminal (PTY) infrastructure service for ScareVerse AI agents.

Provides interactive shell sessions over WebSocket and Git operations over HTTP.
Acts as shared backend for CLI-based AI tools (GeminiCLI, Claude Code, Aider, etc.).

---

## Quick Start

```bash
# 1. Copy env file and configure
cp .env.example .env

# 2. Build and start
docker-compose up -d

# 3. Verify health
curl http://localhost:8000/health
```

---

## WebSocket API

Connect to `ws://<host>:8000/ws`

### Server → Client: init

Sent immediately after connection.

```json
{
  "type": "init",
  "session_id": "uuid-v4",
  "cwd": "/app/artifacts",
  "shell": "/bin/bash"
}
```

### Client → Server: input

Send raw keystrokes (include `\n` for Enter).

```json
{ "type": "input", "data": "ls -la\n" }
```

### Client → Server: resize

Resize the terminal.

```json
{ "type": "resize", "cols": 120, "rows": 40 }
```

### Client → Server: close

Close the session.

```json
{ "type": "close" }
```

### Server → Client: output

Raw terminal output from the shell.

```json
{ "type": "output", "data": "user@host:/app/artifacts$ " }
```

### Server → Client: error

```json
{ "type": "error", "message": "Session timeout" }
```

### Server → Client: closed

```json
{ "type": "closed", "reason": "User closed terminal" }
```

---

## Git HTTP API

### `POST /api/git/status`

```json
// Request
{ "cwd": "myrepo" }

// Response
{ "status": "dirty", "files": [" M src/server.js"], "raw": "..." }
```

### `POST /api/git/log`

```json
// Request
{ "cwd": "myrepo", "limit": 10 }

// Response
{
  "commits": [
    { "hash": "abc123", "author": "Alice", "date": "2024-01-01T00:00:00+00:00", "message": "feat: init" }
  ]
}
```

### `POST /api/git/clone`

```json
// Request
{ "url": "https://github.com/org/repo.git", "dest": "myrepo" }

// Response
{ "success": true, "message": "Cloned https://... → /app/artifacts/myrepo" }
```

---

## Configuration

| Variable           | Default          | Description                              |
|--------------------|------------------|------------------------------------------|
| `PORT`             | `8000`           | HTTP + WebSocket port                    |
| `SESSION_TIMEOUT`  | `3600`           | Idle PTY session timeout (seconds)       |
| `LOG_LEVEL`        | `INFO`           | `DEBUG` / `INFO` / `ERROR`               |
| `ARTIFACTS_PATH`   | `/app/artifacts` | PTY working directory and Git base path  |
| `SHELL`            | `/bin/bash`      | Shell to spawn                           |
| `REDIS_L1_HOST`    | `redis`          | Redis L1 hostname                        |
| `REDIS_L1_PORT`    | `6380`           | Redis L1 port                            |
| `REDIS_L1_PASSWORD`| `scarerunner`    | Redis L1 password                        |
| `HEARTBEAT_INTERVAL`| `20`            | Heartbeat refresh interval (seconds)     |
| `HEARTBEAT_TTL`    | `60`             | Heartbeat key TTL (seconds)              |

---

## Running Tests

```bash
cd artifacts/canonical/services/node-pty-service
npm install
npm test
```

---

## Architecture

```
Frontend (xterm-terminal-cell)
    ↕ WebSocket ws://<host>:8000/ws
Node-PTY Service (this service)
    ├─ PTY Manager  →  node-pty spawned shell
    ├─ Git Helper   →  git subprocess
    └─ Heartbeat    →  Redis L1 (state:service:node-pty-service:available)
        ↓
/app/artifacts (persistent volume)
```
