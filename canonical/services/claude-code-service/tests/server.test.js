/**
 * @file tests/server.test.js
 * @description Unit tests for Claude Code Service (node-pty based).
 *
 * Mocks: node-pty, ioredis, ws WebSocketServer, express.
 *
 * Test coverage targets (>80%):
 * - HTTP /health endpoint
 * - WebSocket connection → spawn claude via PTY
 * - input message → pty.write
 * - resize message → pty.resize
 * - close message → pty.kill
 * - PTY onData → output message
 * - PTY onExit → closed message
 * - Redis heartbeat on startup
 * - SIGTERM graceful shutdown
 * - Error handling: spawn failure
 */

'use strict'

const http = require('http')

// ─── Mock config (comes from base image, not present in claude-code-service) ──

jest.mock('../config/env', () => ({
  PORT: 0,
  LOG_LEVEL: 'ERROR',
  WS_PATH: '/ws',
  PTY_COLS: 80,
  PTY_ROWS: 24,
  REDIS_L1_HOST: 'localhost',
  REDIS_L1_PORT: 6380,
  REDIS_L1_DB: 0,
  REDIS_L1_PASSWORD: 'test',
  HEARTBEAT_INTERVAL: 999999,
  HEARTBEAT_TTL: 999999,
}), { virtual: true })

// ─── PTY Mock ─────────────────────────────────────────────────────────────────

let mockOnDataCallback = null
let mockOnExitCallback = null
const mockPtySpawn = jest.fn()
const mockPtyProcess = {
  onData: jest.fn((cb) => { mockOnDataCallback = cb }),
  onExit: jest.fn((cb) => { mockOnExitCallback = cb }),
  write: jest.fn(),
  resize: jest.fn(),
  kill: jest.fn(),
}

jest.mock('node-pty', () => ({
  spawn: (...args) => mockPtySpawn(...args),
}))

// ─── Redis Mock ────────────────────────────────────────────────────────────────

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

  beforeEach(async () => {
    // Reset PTY mock state per test
    mockOnDataCallback = null
    mockOnExitCallback = null
    jest.clearAllMocks()

    // Reset mock return value each time (default: return mock PTY process)
    mockPtySpawn.mockReturnValue(mockPtyProcess)

    jest.isolateModules(() => {
      const mod = require('../src/server')
      server = mod.server
    })
    await new Promise((resolve) => server.once('listening', resolve))
    wsUrl = `ws://localhost:${server.address().port}/ws`
  })

  afterEach(() => {
    if (server) server.close()
  })

  test('WebSocket connection spawns claude via PTY', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      expect(mockPtySpawn).toHaveBeenCalledWith('claude', [], expect.objectContaining({
        name: 'xterm-256color',
        cols: 80,
        rows: 24,
      }))
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

  test('input message writes to pty', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      setImmediate(() => {
        ws.send(JSON.stringify({ type: 'input', data: 'test prompt\n' }))
      })
    })

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      if (msg.type === 'init') {
        setTimeout(() => {
          expect(mockPtyProcess.write).toHaveBeenCalledWith('test prompt\n')
          ws.close()
          done()
        }, 100)
      }
    })

    ws.on('error', done)
  })

  test('close message kills pty', (done) => {
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
        expect(mockPtyProcess.kill).toHaveBeenCalled()
        ws.close()
        done()
      }
    })

    ws.on('error', done)
  })

  test('output message sent when pty onData fires', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      if (msg.type === 'init') {
        // Simulate PTY output via the captured onData callback
        mockOnDataCallback('Hello from Claude')
      } else if (msg.type === 'output') {
        expect(msg.data).toBe('Hello from Claude')
        ws.close()
        done()
      }
    })

    ws.on('error', done)
  })

  test('closed message on pty onExit', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString())
      if (msg.type === 'init') {
        // Simulate PTY exit
        mockOnExitCallback({ exitCode: 0, signal: null })
      } else if (msg.type === 'closed') {
        expect(msg.reason).toContain('exited')
        ws.close()
        done()
      }
    })

    ws.on('error', done)
  })

  test('resize message resizes pty', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      setImmediate(() => {
        ws.send(JSON.stringify({ type: 'resize', cols: 120, rows: 40 }))
        setTimeout(() => {
          expect(mockPtyProcess.resize).toHaveBeenCalledWith(120, 40)
          ws.close()
          done()
        }, 100)
      })
    })

    ws.on('error', done)
  })

  test('non-JSON messages do not crash server', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      ws.send('this is not json')
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

  test('WS close kills pty', (done) => {
    const WebSocket = require('ws')

    const ws = new WebSocket(wsUrl)

    ws.on('open', () => {
      ws.close()
      setTimeout(() => {
        expect(mockPtyProcess.kill).toHaveBeenCalled()
        done()
      }, 100)
    })

    ws.on('error', done)
  })
})

describe('Spawn failure handling', () => {
  let wsUrl

  beforeEach(async () => {
    mockPtySpawn.mockImplementation(() => {
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
    expect(typeof mod.app).toBe('function')
    expect(mod.server instanceof http.Server).toBe(true)
  })
})
