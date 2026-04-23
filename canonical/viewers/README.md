# Viewers

Canonical viewer artifacts for ScareVerse — standalone Vue.js applications that run inside the ViewerShell iframe context.

## Purpose

This directory contains canonical viewer implementations used in the ScareVerse workspace. Viewers are standalone Vue.js applications that:
- Receive initialization via `postMessage` from the ViewerShell (`INIT_WORKSPACE`)
- Inject session tokens for authenticated API requests
- Render workspace UI within an iframe context
- Are built independently and served via the artifact CDN

## Directory Structure

```
viewers/
├── dynamic-workspace/   - Full-featured dynamic workspace viewer (Vue 3 + Vite)
└── hmr-test/            - Minimal viewer for HMR and postMessage integration testing
```

## How to Use

Each viewer is an independent Vue.js application built with Vite:

```bash
# Build a viewer (from the viewer's directory)
cd artifacts/canonical/viewers/dynamic-workspace
npm install
npm run build

# Or via the canonical build pipeline
make build-viewers
```

### ViewerShell Integration

Viewers communicate with the parent shell via `postMessage`:

```javascript
// Parent → Viewer: Initialize with session
{ type: 'INIT_WORKSPACE', payload: { sessionToken: '...' } }

// Viewer → Parent: Signal readiness
{ type: 'VIEWER_READY' }
```

## Content Index

| Directory | Description |
|---|---|
| `dynamic-workspace/` | Full dynamic workspace viewer with grid layout, auto-save, and cell loading |
| `hmr-test/` | Minimal test viewer for validating HMR and postMessage session injection |
