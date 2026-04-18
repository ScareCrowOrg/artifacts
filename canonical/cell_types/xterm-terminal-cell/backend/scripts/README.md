# Xterm Terminal Cell – Backend Scripts

## Purpose

Entry point for the **Xterm Terminal Cell** backend — PTY management and WebSocket bridging.

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`main.py`](./main.py) | PTY lifecycle: `spawn_pty()`, `handle_websocket()`, stdin/stdout forwarding, terminal resize events |

## Related

- [`../`](../) — Xterm Terminal Cell backend root
