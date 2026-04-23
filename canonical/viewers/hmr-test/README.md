# HMR Test Viewer

A minimal Vue.js viewer for validating Hot Module Replacement (HMR) and `postMessage`-based session injection in the ScareVerse ViewerShell context.

## Purpose

This viewer is a lightweight diagnostic tool used during development to:
- Validate that the ViewerShell correctly sends `INIT_WORKSPACE` with a session token
- Verify that HMR works correctly inside the iframe context
- Test WebSocket connectivity after session validation
- Serve as a reference implementation for the minimal viewer contract

## Directory Structure

```
hmr-test/
├── App.vue      - Root Vue component; displays session and WebSocket status
├── main.ts      - Entry point; listens for INIT_WORKSPACE before mounting
└── index.html   - HTML shell for Vite dev server
```

## How to Use

```bash
# Start in development mode (from the hmr-test directory)
npm run dev

# Or build for production
npm run build
```

The viewer displays a status panel showing:
- Whether the `INIT_WORKSPACE` message was received
- Whether the session token was injected
- WebSocket connection status

## Content Index

| File | Description |
|---|---|
| `App.vue` | Status display component showing session and connection state |
| `main.ts` | Entry point; defers app mount until session token is received |
| `index.html` | Vite HTML entry point |
