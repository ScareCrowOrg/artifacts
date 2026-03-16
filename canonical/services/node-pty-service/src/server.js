/**
 * @file src/server.js
 * @description Node-PTY Service main entry point.
 *
 * Starts an Express HTTP server and a WebSocket server on the same port.
 *
 * HTTP endpoints:
 *   GET  /health          - Liveness check
 *   POST /api/git/status  - Git status
 *   POST /api/git/log     - Git log
 *   POST /api/git/clone   - Git clone
 *
 * WebSocket endpoint:
 *   ws://<host>:<port>/ws  - Interactive PTY session
 *
 * Message protocol (JSON):
 *   Client → Server: { type: "input"|"resize"|"close", data?, cols?, rows? }
 *   Server → Client: { type: "init"|"output"|"error"|"closed", ... }
 *
 * Heartbeat:
 *   Registers state:service:node-pty-service:available in Redis L1 every
 *   HEARTBEAT_INTERVAL seconds (TTL = HEARTBEAT_TTL seconds).
 */

'use strict'

require('dotenv').config()

const http = require('http')
const express = require('express')
const { WebSocketServer, WebSocket } = require('ws')
const Redis = require('ioredis')
const config = require('../config/env')
const ptyManager = require('./ptyManager')
const gitHelper = require('./gitHelper')

// ─── Logging helper ───────────────────────────────────────────────────────────

const LOG_LEVEL = (config.LOG_LEVEL || 'INFO').toUpperCase()

function log(level, message) {
  if (LOG_LEVEL === 'ERROR' && level !== 'ERROR') return
  if (LOG_LEVEL === 'INFO' && level === 'DEBUG') return
  console.log(`[${new Date().toISOString()}] [Server] [${level}] ${message}`)
}

// ─── Express app ─────────────────────────────────────────────────────────────

const app = express()
app.use(express.json())

app.get('/health', (_req, res) => {
  res.json({
    status: 'healthy',
    service: 'node-pty-service',
    sessions: ptyManager.count(),
    uptime: process.uptime(),
  })
})

app.post('/api/git/status', async (req, res) => {
  try {
    const result = await gitHelper.status(req.body)
    res.json(result)
  } catch (err) {
    log('ERROR', `git/status failed: ${err.message}`)
    res.status(500).json({ error: 'Git status operation failed' })
  }
})

app.post('/api/git/log', async (req, res) => {
  try {
    const result = await gitHelper.log(req.body)
    res.json(result)
  } catch (err) {
    log('ERROR', `git/log failed: ${err.message}`)
    res.status(500).json({ error: 'Git log operation failed' })
  }
})

app.post('/api/git/clone', async (req, res) => {
  try {
    const result = await gitHelper.clone(req.body)
    res.json(result)
  } catch (err) {
    log('ERROR', `git/clone failed: ${err.message}`)
    res.status(500).json({ error: 'Git clone operation failed' })
  }
})

// ─── HTTP server ─────────────────────────────────────────────────────────────

const server = http.createServer(app)

// ─── WebSocket server ─────────────────────────────────────────────────────────

const wss = new WebSocketServer({ server, path: config.WS_PATH })

wss.on('connection', (ws) => {
  let sessionId = null

  try {
    const sessionInfo = ptyManager.create()
    sessionId = sessionInfo.session_id

    log('INFO', `WebSocket connected → session ${sessionId}`)

    send(ws, {
      type: 'init',
      session_id: sessionId,
      cwd: sessionInfo.cwd,
      shell: sessionInfo.shell,
    })

    ptyManager.onData(sessionId, (data) => {
      send(ws, { type: 'output', data })
    })

    ptyManager.onExit(sessionId, (exitCode, signal) => {
      send(ws, { type: 'closed', reason: `Process exited (code=${exitCode}, signal=${signal})` })
      ws.close()
    })
  } catch (err) {
    log('ERROR', `Failed to create PTY session: ${err.message}`)
    send(ws, { type: 'error', message: 'Failed to create terminal session' })
    ws.close()
    return
  }

  ws.on('message', (raw) => {
    let msg
    try {
      msg = JSON.parse(raw.toString())
    } catch {
      log('DEBUG', `Received non-JSON message`)
      return
    }

    try {
      switch (msg.type) {
        case 'input':
          if (typeof msg.data === 'string' && sessionId) {
            ptyManager.write(sessionId, msg.data)
          }
          break

        case 'resize':
          if (sessionId && typeof msg.cols === 'number' && typeof msg.rows === 'number') {
            ptyManager.resize(sessionId, msg.cols, msg.rows)
          }
          break

        case 'close':
          if (sessionId) {
            ptyManager.close(sessionId)
            send(ws, { type: 'closed', reason: 'User closed terminal' })
            ws.close()
          }
          break

        default:
          log('DEBUG', `Unknown message type: ${msg.type}`)
      }
    } catch (err) {
      log('ERROR', `Error handling message (type=${msg.type}): ${err.message}`)
      send(ws, { type: 'error', message: 'Internal server error' })
    }
  })

  ws.on('close', () => {
    log('INFO', `WebSocket closed → session ${sessionId}`)
    if (sessionId && ptyManager.has(sessionId)) {
      ptyManager.close(sessionId)
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

    const key = 'state:service:node-pty-service:available'
    const interval = config.HEARTBEAT_INTERVAL * 1000

    async function beat() {
      try {
        await redisClient.set(key, '1', 'EX', config.HEARTBEAT_TTL)
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

  ptyManager.closeAll()

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
  log('INFO', `Node-PTY Service listening on port ${config.PORT}`)
  log('INFO', `WebSocket endpoint: ws://0.0.0.0:${config.PORT}${config.WS_PATH}`)
  log('INFO', `Artifacts path: ${config.ARTIFACTS_PATH}`)
  await startHeartbeat()
})

module.exports = { app, server, wss }
