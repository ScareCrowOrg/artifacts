/**
 * @file src/server.js
 * @description Claude Code Service main entry point.
 *
 * Starts an Express HTTP server and a WebSocket server on the same port.
 * Uses node-pty to spawn the Claude Code CLI in a pseudo-terminal so it
 * runs in interactive (TTY) mode — without a PTY the Claude CLI auto-detects
 * non-TTY, enters --print (one-shot) mode, and exits after one response.
 *
 * HTTP endpoints:
 *   GET  /health  - Liveness check
 *
 * WebSocket endpoint:
 *   ws://<host>:<port>/ws  - Interactive Claude Code session
 *
 * Each WebSocket connection spawns a `claude` subprocess via node-pty and
 * pipes terminal I/O between the WebSocket and the Claude Code CLI.
 *
 * Message protocol (JSON):
 *   Client → Server: { type: "input"|"resize"|"close", data?, cols?, rows? }
 *   Server → Client: { type: "init"|"output"|"error"|"closed", ... }
 *
 * Heartbeat:
 *   Registers state:service:claude-code-service:available in Redis L1 every
 *   HEARTBEAT_INTERVAL seconds (TTL = HEARTBEAT_TTL seconds).
 */

'use strict'

require('dotenv').config()

const http = require('http')
const express = require('express')
const { WebSocketServer, WebSocket } = require('ws')
const pty = require('node-pty')
const Redis = require('ioredis')
const crypto = require('crypto')
const config = require('../config/env')

// ─── Logging helper ───────────────────────────────────────────────────────────

const LOG_LEVEL = (config.LOG_LEVEL || 'INFO').toUpperCase()

function log(level, message) {
  if (LOG_LEVEL === 'ERROR' && level !== 'ERROR') return
  if (LOG_LEVEL === 'INFO' && level === 'DEBUG') return
  console.log(`[${new Date().toISOString()}] [ClaudeCodeService] [${level}] ${message}`)
}

// ─── Express app ─────────────────────────────────────────────────────────────

const app = express()
app.use(express.json())

app.get('/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'claude-code-service',
    uptime: process.uptime(),
  })
})

// ─── HTTP server ─────────────────────────────────────────────────────────────

const server = http.createServer(app)

// ─── WebSocket server ─────────────────────────────────────────────────────────

const wss = new WebSocketServer({ server, path: config.WS_PATH })

// Track active claude processes for graceful shutdown
const activeProcesses = new Map()

wss.on('connection', (ws) => {
  const sessionId = crypto.randomUUID()
  let ptyProcess = null

  try {
    log('INFO', `WebSocket connected → session ${sessionId}`)

    const cols = config.PTY_COLS || 80
    const rows = config.PTY_ROWS || 24

    const env = {
      ...process.env,
      HOME: process.env.CLAUDE_HOME || '/app/artifacts',
      TERM: 'xterm-256color',
    }

    // Spawn Claude CLI in a PTY so it runs interactively (TTY mode).
    // Without a PTY, Claude auto-detects non-TTY stdin/stdout, enters
    // --print (one-shot) mode, and exits after a single response.
    ptyProcess = pty.spawn('claude', [], {
      name: 'xterm-256color',
      cols,
      rows,
      env,
      cwd: process.env.CLAUDE_HOME || '/app/artifacts',
    })

    activeProcesses.set(sessionId, ptyProcess)

    // PTY output → WebSocket (includes both stdout and stderr)
    ptyProcess.onData((data) => {
      send(ws, { type: 'output', data })
    })

    // PTY exit → WebSocket closed
    ptyProcess.onExit(({ exitCode, signal }) => {
      activeProcesses.delete(sessionId)
      log('INFO', `Claude process exited (session=${sessionId}, code=${exitCode}, signal=${signal})`)
      send(ws, { type: 'closed', reason: `Claude process exited (code=${exitCode}, signal=${signal})` })
      try { ws.close() } catch {}
    })

    // Send init — the PTY is ready immediately after spawn
    send(ws, {
      type: 'init',
      session_id: sessionId,
    })
  } catch (err) {
    log('ERROR', `Failed to spawn claude process: ${err.message}`)
    send(ws, { type: 'error', message: `Failed to start Claude Code: ${err.message}` })
    ws.close()
    return
  }

  ws.on('message', (raw) => {
    let msg
    try {
      msg = JSON.parse(raw.toString())
    } catch {
      log('DEBUG', `Received non-JSON message from session ${sessionId}`)
      return
    }

    try {
      switch (msg.type) {
        case 'input':
          if (typeof msg.data === 'string' && ptyProcess) {
            ptyProcess.write(msg.data)
          }
          break

        case 'resize':
          if (typeof msg.cols === 'number' && typeof msg.rows === 'number' && ptyProcess) {
            ptyProcess.resize(msg.cols, msg.rows)
          }
          break

        case 'close':
          if (ptyProcess) {
            ptyProcess.kill()
            send(ws, { type: 'closed', reason: 'User closed session' })
            try { ws.close() } catch {}
          }
          break

        default:
          log('DEBUG', `Unknown message type: ${msg.type} (session=${sessionId})`)
      }
    } catch (err) {
      log('ERROR', `Error handling message (session=${sessionId}, type=${msg.type}): ${err.message}`)
      send(ws, { type: 'error', message: 'Internal server error' })
    }
  })

  ws.on('close', () => {
    log('INFO', `WebSocket closed → session ${sessionId}`)
    if (ptyProcess) {
      activeProcesses.delete(sessionId)
      try { ptyProcess.kill() } catch {}
    }
  })

  ws.on('error', (err) => {
    log('ERROR', `WebSocket error (session=${sessionId}): ${err.message}`)
  })
})

// ─── Redis heartbeat ─────────────────────────────────────────────────────────

let redisClient = null
let heartbeatTimer = null

async function startHeartbeat() {
  try {
    redisClient = new Redis({
      host: config.REDIS_L1_HOST,
      port: config.REDIS_L1_PORT,
      db: config.REDIS_L1_DB,
      password: config.REDIS_L1_PASSWORD || undefined,
      lazyConnect: true,
      enableOfflineQueue: false,
    })

    redisClient.on('error', (err) => {
      log('ERROR', `Redis error: ${err.message}`)
    })

    await redisClient.connect()

    const key = 'state:service:claude-code-service:available'
    const interval = config.HEARTBEAT_INTERVAL * 1000

    async function beat() {
      try {
        const value = JSON.stringify({
          port_opened: true,
          wss_pty: true,
          timestamp: Date.now() / 1000,
        })
        await redisClient.set(key, value, 'EX', config.HEARTBEAT_TTL)
        log('DEBUG', `Heartbeat: set ${key} (TTL=${config.HEARTBEAT_TTL}s)`)
      } catch (err) {
        log('ERROR', `Heartbeat failed: ${err.message}`)
      }
    }

    await beat()
    heartbeatTimer = setInterval(beat, interval)
    if (heartbeatTimer.unref) heartbeatTimer.unref()

    log('INFO', `Redis heartbeat started (key=${key}, interval=${config.HEARTBEAT_INTERVAL}s)`)
  } catch (err) {
    log('ERROR', `Could not connect to Redis: ${err.message}. Heartbeat disabled.`)
  }
}

// ─── Send helper ─────────────────────────────────────────────────────────────

function send(ws, payload) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload))
  }
}

// ─── Graceful shutdown ────────────────────────────────────────────────────────

function shutdown(signal) {
  log('INFO', `Received ${signal}, shutting down…`)

  if (heartbeatTimer) clearInterval(heartbeatTimer)
  if (redisClient) {
    redisClient.quit().catch(() => {})
  }

  // Kill all active claude processes
  for (const [sessionId, proc] of activeProcesses) {
    try { proc.kill() } catch {}
  }
  activeProcesses.clear()

  server.close(() => {
    log('INFO', 'HTTP server closed')
    process.exit(0)
  })

  setTimeout(() => process.exit(1), 5000).unref()
}

process.on('SIGTERM', () => shutdown('SIGTERM'))
process.on('SIGINT', () => shutdown('SIGINT'))

// ─── Start ────────────────────────────────────────────────────────────────────

server.listen(config.PORT, '0.0.0.0', async () => {
  log('INFO', `Claude Code Service listening on port ${config.PORT}`)
  log('INFO', `WebSocket endpoint: ws://0.0.0.0:${config.PORT}${config.WS_PATH}`)
  await startHeartbeat()
})

module.exports = { app, server, wss }
