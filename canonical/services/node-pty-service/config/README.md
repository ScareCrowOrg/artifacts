# Node-PTY Service Configuration

Configuration module for the Node-PTY Service, providing default values and environment variable resolution.

## Purpose

This directory defines configuration for the Node-PTY Service:
- **Default values**: Sensible defaults for all service parameters (port, timeouts, session limits)
- **Environment resolution**: Merges environment variables over defaults for runtime configuration
- **Type safety**: Parses integer and boolean env vars with fallback to defaults

## Directory Structure

```
config/
├── defaults.js  - Default configuration values for all service parameters
└── env.js       - Environment variable loader and merger with defaults
```

## How to Use

Configuration is loaded automatically by `src/server.js`:

```javascript
const config = require('./config/env')
// config.PORT, config.MAX_SESSIONS, config.HEARTBEAT_INTERVAL, etc.
```

### Key Configuration Parameters

| Parameter | Default | Description |
|---|---|---|
| `PORT` | `8000` | HTTP/WebSocket server port |
| `MAX_SESSIONS` | `50` | Maximum concurrent PTY sessions |
| `SESSION_TIMEOUT` | `3600` | Seconds before idle session is closed |
| `HEARTBEAT_INTERVAL` | `20` | Seconds between Redis L1 heartbeat refreshes |
| `HEARTBEAT_TTL` | `60` | Redis key TTL in seconds |
| `SHELL` | `/bin/bash` | Shell used for PTY sessions |
| `WS_PATH` | `/ws` | WebSocket endpoint path |

## Content Index

| File | Description |
|---|---|
| `defaults.js` | Default configuration values for all service parameters |
| `env.js` | Environment variable loader with type parsing and default merging |
