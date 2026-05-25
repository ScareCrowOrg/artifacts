# Claude Code Service

WebSocket PTY service for Claude Code CLI. Baixa e instala o Claude Code
automaticamente no entrypoint e expõe um terminal WebSocket para interação.

## Architecture

```
entrypoint.sh
  ├─ Verifica se `claude` está instalado
  ├─ Se não: testa conectividade HTTPS (diagnóstico CA certs)
  │  └─ npm install -g @anthropic-ai/claude-code
  ├─ Warning se ANTHROPIC_API_KEY não estiver setada
  └─ Inicia: node src/server.js

src/server.js
  ├─ Express: GET /health → { status, service, uptime }
  ├─ WebSocketServer: path configurável (default /ws)
  │  └─ Cada conexão spawna `claude` via node-pty (TTY mode)
  ├─ Redis: heartbeat state:service:claude-code-service:available
  └─ Graceful shutdown (SIGTERM/SIGINT → kill PTYs, quit Redis)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | HTTP/WebSocket server port |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, ERROR) |
| `CLAUDE_HOME` | `/app/claude-home` | Claude Code home directory (cache volume, `~/.claude/`) |
| `CLAUDE_CWD` | `/app/artifacts` | PTY working directory (onde o Claude Code abre) |
| `WS_PATH` | `/ws` | WebSocket endpoint path |
| `PTY_COLS` | `80` | PTY columns (terminal width) |
| `PTY_ROWS` | `24` | PTY rows (terminal height) |
| `REDIS_L1_HOST` | `redis` | Redis L1 host for heartbeat |
| `REDIS_L1_PORT` | `6380` | Redis L1 port |
| `REDIS_L1_DB` | `0` | Redis L1 database index |
| `REDIS_L1_PASSWORD` | `scarerunner` | Redis L1 password |
| `HEARTBEAT_INTERVAL` | `20` | Seconds between heartbeat refreshes |
| `HEARTBEAT_TTL` | `60` | Redis key TTL in seconds |
| `ANTHROPIC_API_KEY` | — | **Required.** Anthropic API key |
| `ANTHROPIC_BASE_URL` | `https://api.deepseek.com/anthropic` | API endpoint |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `deepseek-v4-flash` | Model mapping for Haiku tier |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | `deepseek-v4-flash` | Model mapping for Sonnet tier |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | `deepseek-v4-pro` | Model mapping for Opus tier |
| `ANTHROPIC_MODEL` | `deepseek-v4-flash` | Default session model |
| `CLAUDE_AUTO_COMPACT_PCT_OVERRIDE` | `95` | Context compaction threshold |

## WebSocket Protocol

**Client → Server:**
- `{ "type": "input", "data": "text\n" }` — Send input to Claude
- `{ "type": "resize", "cols": 120, "rows": 40 }` — Resize PTY dimensions
- `{ "type": "close" }` — Close session

**Server → Client:**
- `{ "type": "init", "session_id": "uuid" }` — Session started, PTY ready
- `{ "type": "output", "data": "stdout" }` — Claude output (stdout + stderr)
- `{ "type": "error", "message": "..." }` — Internal error (spawn failure, etc.)
- `{ "type": "closed", "reason": "..." }` — Session ended

## Heartbeat

Registers `state:service:claude-code-service:available` in Redis L1 with JSON payload:
```json
{
  "port_opened": true,
  "wss_pty": true,
  "timestamp": 1234567890.123
}
```

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
