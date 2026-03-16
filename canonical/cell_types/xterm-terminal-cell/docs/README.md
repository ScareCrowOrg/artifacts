# xterm-terminal-cell

Interactive terminal cell for ScareVerse Cockpit powered by [xterm.js](https://xtermjs.org/).

Provides persistent shell sessions through the **Node-PTY Service** over WebSocket.
Acts as the UI entry point for AI agent CLI tools (GeminiCLI, Claude Code, Aider, etc.).

---

## Usage

Add the cell to a notebook. It will automatically connect to the Node-PTY service
WebSocket on mount.

### Initial Data

```json
{
  "ws_url": "ws://node-pty-service:8000/ws",
  "cols": 120,
  "rows": 40,
  "font_size": 14,
  "theme": "dark"
}
```

### Properties

| Property    | Type    | Default                              | Description                          |
|-------------|---------|--------------------------------------|--------------------------------------|
| `ws_url`    | string  | `ws://node-pty-service:8000/ws`      | Node-PTY service WebSocket endpoint  |
| `cols`      | integer | `120`                                | Terminal columns                     |
| `rows`      | integer | `40`                                 | Terminal rows                        |
| `font_size` | integer | `14`                                 | Font size in pixels                  |
| `theme`     | string  | `dark`                               | `dark` or `light`                    |

---

## Architecture

```
View.vue (xterm-terminal-cell)
  │
  │  WebSocket  ws://node-pty-service:8000/ws
  │
  ▼
Node-PTY Service (node-pty-service)
  ├─ PTY Manager  →  spawned /bin/bash
  └─ Heartbeat    →  Redis L1
       ▼
  /app/artifacts  (persistent volume)
```

---

## WebSocket Message Protocol

### After connection: server sends `init`

```json
{
  "type": "init",
  "session_id": "uuid",
  "cwd": "/app/artifacts",
  "shell": "/bin/bash"
}
```

### User input → server

```json
{ "type": "input", "data": "ls -la\n" }
```

### Terminal resize

```json
{ "type": "resize", "cols": 120, "rows": 40 }
```

### Server output → terminal

```json
{ "type": "output", "data": "user@host:~$ " }
```

---

## Dependencies

- **Runtime**: Node-PTY Service must be running and accessible on `scareverse-net`
- **Frontend packages**: `xterm`, `xterm-addon-fit` (installed in cockpit-vue)

## Running Tests

```bash
# Frontend (Vitest)
cd cockpit-vue && npm run test:unit -- --testPathPattern=xterm-terminal-cell

# Backend (pytest)
cd artifacts/canonical/cell_types/xterm-terminal-cell
pytest backend/tests/
```
