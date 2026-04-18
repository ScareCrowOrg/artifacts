# Xterm Terminal Cell – Backend

## Purpose

Python backend for the **Xterm Terminal Cell** — provides the WebSocket-based PTY (pseudo-terminal) service that powers the terminal UI.

## Content Index

| Directory | Description |
|-----------|-------------|
| [`scripts/`](./scripts/) | `main.py` — PTY management: `spawn_pty()`, handle `stdin`/`stdout` over WebSocket, resize events |
| [`tests/`](./tests/) | `test_main.py` — backend unit tests |

## Architecture

The frontend `View.vue` establishes a WebSocket connection → Backend creates a PTY process → stdin/stdout are bridged over the WebSocket → xterm.js renders the terminal output.

## Related

- [`../`](../) — Xterm Terminal Cell root
- [`../frontend/`](../frontend/) — Frontend that establishes the WebSocket connection
