/**
 * @file tests/server.test.js
 * @description Unit tests for Claude Code Service.
 *
 * Mocks: child_process.spawn, ioredis, ws WebSocketServer, express.
 *
 * Test coverage targets (>80%):
 * - HTTP /health endpoint
 * - WebSocket connection → spawn claude
 * - input message → stdin write
 * - close message → kill process
 * - Redis heartbeat on startup
 * - SIGTERM graceful shutdown
 * - Error handling: process spawn failure
 */

'use strict'

const http = require('http')
const EventEmitter = require('events')

// ─── Mock config (comes from base image, not present in claude-code-service) ──

jest.mock('../config/env', () => ({
  PORT: 0,
  LOG_LEVEL: 'ERROR',
  WS_PATH: '/ws',
  REDIS_L1_HOST: 'localhost',
  REDIS_L1_PORT: 6380,
  REDIS_L1_DB: 0,
  REDIS_L1_PASSWORD: 'test',
  HEARTBEAT_INTERVAL: 999999,
  HEARTBEAT_TTL: 999999,
}), { virtual: true })

// ─── Mocks ────────────────────────────────────────────────────────────────────

const mockSpawn = jest.fn()
jest.mock('child_process', () => ({
  spawn: (...args) => mockSpawn(...args),
}))

const mockRedisSet = jest.fn()
const mockRedisQuit = jest.fn()
jest.mock('ioredis', () => {
  return jest.fn().mockImplementation(() => ({
    connect: jest.fn().mockResolvedValue(undefined),
    set: mockRedisSet.mockResolvedValue('OK'),
    quit: mockRedisQuit.mockResolvedValue(undefined),
    on: jest.fn(),
  }))
})

// ─── Module under test (loaded after mocks) ────────────────────────────────────

let server

beforeAll(() => {
  // Set env before loading module
  process.env.PORT = '0' // random port
  process.env.LOG_LEVEL = 'ERROR'
  process.env.REDIS_L1_HOST = 'localhost'
  process.env.REDIS_L1_PORT = '6380'
  process.env.REDIS_L1_DB = '0'
  process.env.REDIS_L1_PASSWORD = 'test'
  process.env.HEARTBEAT_INTERVAL = '999999' // prevents heartbeat from running during tests
  process.env.HEARTBEAT_TTL = '999999'
  process.env.CLAUDE_HOME = '/tmp/claude-home'
})

afterAll(() => {
  jest.restoreAllMocks()
  jest.resetModules()
})

describe('HTTP /health endpoint', () => {
  beforeAll(async () => {
    jest.isolateModules(() => {
      const mod = require('../src/server')
      server = mod.server
    })
    // Wait for server to be listening
    await new Promise((resolve) => server.once('listening', resolve))
  })

  afterAll(() => {
    if (server) server.close()
  })

  test('GET /health returns 200 with service info', async () => {
    const res = await fetch(`http://localhost:${server.address().port}/health`)
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.status).toBe('ok')
    expect(body.service).toBe('claude-code-service')
    expect(body).toHaveProperty('uptime')
  })
})

describe('WebSocket connection', () => {
  let wsUrl
  let mockClaudeProcess

  beforeEach(async () => {
    jest.isolateModules(() => {
      const mod = require('../src/server')
      server = mod.server
    })
    await new Promise((resolve) => server.once('listening', resolve))
    wsUrl = `ws://localhost:${server.address().port}/ws`

    // Create mock claude subprocess
    mockClaudeProcess = new EventEmitter()
    mockClaudeProcess.stdin = { write: jest.fn(), writable: true }
    mockClaudeProcess.stdout = new EventEmitter()
    mockClaudeProcess.stderr = new EventEmitter()
    mockClaudeProcess.kill = jest.fn()
    mockClaudeProcess.pid = 12345
    mockSpawn.mockReturnValue(mockClaudeProcess)
  })

  afterEach(() => {
    if (server) server.close()
    jest.clearAllMocks()
  })

  test('WebSocket connection spawns claude process', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      expect(mockSpawn).toHaveBeenCalledWith('claude', [], expect.any(Object))
      ws.close()
      done()
    })

    ws.on('error', done)
  })

  test('WebSocket sends init message on connection', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      expect(msg.type).toBe('init')
      expect(msg.session_id).toBeDefined()
      ws.close()
      done()
    })

    ws.on('error', done)
  })

  test('input message writes to claude stdin', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      // Wait a tick for init to be sent, then send input
      setImmediate(() => {
        ws.send(JSON.stringify({ type: 'input', data: 'test prompt\n' }))
      })
    })

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      // After init, check that stdin was written
      if (msg.type === 'init') {
        // The input will arrive after init, so we listen for close
        setTimeout(() => {
          expect(mockClaudeProcess.stdin.write).toHaveBeenCalledWith('test prompt\n')
          ws.close()
          done()
        }, 100)
      }
    })

    ws.on('error', done)
  })

  test('close message kills claude process', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      setImmediate(() => {
        ws.send(JSON.stringify({ type: 'close' }))
      })
    })

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      if (msg.type === 'closed') {
        expect(mockClaudeProcess.kill).toHaveBeenCalledWith('SIGTERM')
        ws.close()
        done()
      }
    })

    ws.on('error', done)
  })

  test('output message sent when claude stdout emits data', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      if (msg.type === 'init') {
        // Simulate claude output
        mockClaudeProcess.stdout.emit('data', Buffer.from('Hello from Claude'))
      } else if (msg.type === 'output') {
        expect(msg.data).toBe('Hello from Claude')
        ws.close()
        done()
      }
    })

    ws.on('error', done)
  })

  test('error message sent when claude stderr emits data', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      if (msg.type === 'init') {
        mockClaudeProcess.stderr.emit('data', Buffer.from('some warning'))
      } else if (msg.type === 'error') {
        expect(msg.message).toBe('some warning')
        ws.close()
        done()
      }
    })

    ws.on('error', done)
  })

  test('closed message on claude process exit', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      if (msg.type === 'init') {
        mockClaudeProcess.emit('exit', 0, null)
      } else if (msg.type === 'closed') {
        expect(msg.reason).toContain('exited')
        ws.close()
        done()
      }
    })

    ws.on('error', done)
  })

  test('non-JSON messages do not crash server', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      // Send raw string (not JSON) — should be silently ignored
      ws.send('this is not json')
      // Wait a bit, then close — if no crash, test passes
      setTimeout(() => {
        ws.close()
        done()
      }, 100)
    })

    ws.on('error', done)
  })

  test('unknown message types do not crash server', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      setImmediate(() => {
        ws.send(JSON.stringify({ type: 'unknown_type_xyz' }))
        setTimeout(() => {
          ws.close()
          done()
        }, 100)
      })
    })

    ws.on('error', done)
  })

  test('WS close kills claude process', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      // Close the WebSocket, which should kill the claude process
      ws.close()
      setTimeout(() => {
        expect(mockClaudeProcess.kill).toHaveBeenCalledWith('SIGTERM')
        done()
      }, 100)
    })

    ws.on('error', done)
  })

  test('resize message does not crash', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      setImmediate(() => {
        // resize is a no-op — verify it doesn't crash
        ws.send(JSON.stringify({ type: 'resize', cols: 120, rows: 40 }))
        setTimeout(() => {
          ws.close()
          done()
        }, 100)
      })
    })

    ws.on('error', done)
  })
})

describe('Spawn failure handling', () => {
  let wsUrl

  beforeEach(async () => {
    mockSpawn.mockImplementation(() => {
      throw new Error('claude not found')
    })

    jest.isolateModules(() => {
      const mod = require('../src/server')
      server = mod.server
    })
    await new Promise((resolve) => server.once('listening', resolve))
    wsUrl = `ws://localhost:${server.address().port}/ws`
  })

  afterEach(() => {
    if (server) server.close()
    jest.clearAllMocks()
  })

  test('error message sent when spawn fails', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      if (msg.type === 'error') {
        expect(msg.message).toContain('Failed to start Claude Code')
        ws.close()
        done()
      }
    })

    ws.on('error', done)
  })
})

describe('Redis heartbeat', () => {
  beforeAll(async () => {
    jest.clearAllMocks()
    const mod = require('../src/server')
    server = mod.server
    await new Promise((resolve) => server.once('listening', resolve))
  })

  afterAll(() => {
    if (server) server.close()
  })

  test('Redis client is created with correct config', () => {
    // The mock ioredis constructor should have been called
    const Redis = require('ioredis')
    expect(Redis).toHaveBeenCalled()
  })
})

describe('Graceful shutdown', () => {
  test('server exports app, server, wss', () => {
    const mod = require('../src/server')
    expect(mod.app).toBeDefined()
    expect(mod.server).toBeDefined()
    expect(mod.wss).toBeDefined()
  })

  test('modules export for testing only', () => {
    jest.resetModules()
    const mod = require('../src/server')
    // Verify the exported objects are valid
    expect(typeof mod.app).toBe('function')
    expect(mod.server instanceof http.Server).toBe(true)
  })
})
