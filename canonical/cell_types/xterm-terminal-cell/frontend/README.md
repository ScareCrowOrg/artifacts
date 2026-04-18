# Xterm Terminal Cell – Frontend

## Purpose

Vue 3 frontend for the **Xterm Terminal Cell** — a UI-only BaseCell that renders an xterm.js terminal connected to a backend PTY via WebSocket. The `execute()` method is a no-op since the terminal self-manages via its WebSocket connection.

## Content Index

| File | Description |
|------|-------------|
| [`xterm-terminal.ts`](./xterm-terminal.ts) | BaseCell implementation — UI-only, no-op `execute()`; provides metadata and health check; WebSocket is managed in `View.vue` |
| [`View.vue`](./View.vue) | Main component — xterm.js terminal instance, WebSocket connection lifecycle, resize handling, theme integration |
| [`composables.ts`](./composables.ts) | Terminal composables — `useTerminal()` for xterm.js initialization and WebSocket management |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`tests/`](./tests/) | `View.spec.ts` — component tests |

## Related

- [`../`](../) — Xterm Terminal Cell root
- [`../backend/`](../backend/) — PTY service that the WebSocket connects to
