# Claude Code Service

WebSocket PTY service for Claude Code CLI. Baixa e instala o Claude Code
automaticamente no entrypoint e expõe um terminal WebSocket para interação.

## Architecture

```
entrypoint.sh
  ├─ Verifica se `claude` está instalado
  ├─ Se não: npm install -g @anthropic-ai/claude-code
  └─ Inicia: node src/server.js

src/server.js
  ├─ Express: GET /health → { status: "ok", service: "claude-code-service" }
  ├─ WebSocket: /ws → spawna claude como subprocess
  ├─ Redis: heartbeat state:service:claude-code-service:available
  └─ Graceful shutdown (SIGTERM)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | HTTP/WebSocket server port |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, ERROR) |
| `CLAUDE_HOME` | `/app/claude-home` | Claude Code home directory (cache volume) |
| `REDIS_L1_HOST` | `redis` | Redis L1 host for heartbeat |
| `REDIS_L1_PORT` | `6380` | Redis L1 port |
| `HEARTBEAT_INTERVAL` | `20` | Seconds between heartbeat refreshes |
| `HEARTBEAT_TTL` | `60` | Redis key TTL in seconds |
| `ANTHROPIC_API_KEY` | — | **Required.** Anthropic API key |
| `ANTHROPIC_BASE_URL` | `https://api.deepseek.com/anthropic` | API endpoint |
| `ANTHROPIC_MODEL` | `deepseek-v4-flash` | Default session model |

## WebSocket Protocol

**Client → Server:**
- `{ "type": "input", "data": "text\n" }` — Send input to Claude
- `{ "type": "close" }` — Close session

**Server → Client:**
- `{ "type": "init", "session_id": "uuid" }` — Session started
- `{ "type": "output", "data": "stdout" }` — Claude output
- `{ "type": "error", "message": "..." }` — Claude stderr
- `{ "type": "closed", "reason": "..." }` — Session ended

## Development

```bash
# Install dependencies
npm install

# Run tests
npm test

# Start locally
npm start
```

## License

MIT
