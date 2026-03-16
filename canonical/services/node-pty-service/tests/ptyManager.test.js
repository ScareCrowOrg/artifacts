/**
 * @file tests/ptyManager.test.js
 * @description Unit tests for PTYManager.
 *
 * node-pty is mocked to avoid spawning real shells during CI.
 */

'use strict'

// ─── Top-level mocks (Jest hoists these before imports) ───────────────────────

// Track spawned MockPTY instances so tests can emit data/exit events
const spawnedInstances = []

jest.mock('node-pty', () => {
  function MockPTY() {
    this._dataHandlers = []
    this._exitHandlers = []
    this.written = []
    this.resized = []
    this.killed = false
    spawnedInstances.push(this)
  }

  MockPTY.prototype.onData = function (cb) {
    this._dataHandlers.push(cb)
    return { dispose: () => {} }
  }

  MockPTY.prototype.onExit = function (cb) {
    this._exitHandlers.push(cb)
    return { dispose: () => {} }
  }

  MockPTY.prototype.write = function (data) {
    this.written.push(data)
  }

  MockPTY.prototype.resize = function (cols, rows) {
    this.resized.push({ cols, rows })
  }

  MockPTY.prototype.kill = function () {
    this.killed = true
  }

  MockPTY.prototype._emitData = function (data) {
    this._dataHandlers.forEach((h) => h(data))
  }

  MockPTY.prototype._emitExit = function (exitCode, signal) {
    this._exitHandlers.forEach((h) => h({ exitCode, signal }))
  }

  return {
    spawn: jest.fn((_shell, _args, _opts) => new MockPTY()),
  }
})

jest.mock('../config/env', () => ({
  PTY_COLS: 80,
  PTY_ROWS: 24,
  ARTIFACTS_PATH: '/tmp/test-artifacts',
  SHELL: '/bin/bash',
  SESSION_TIMEOUT: 0, // disable timeouts in tests
  LOG_LEVEL: 'ERROR',
}))

// ─── Import module under test ─────────────────────────────────────────────────

const manager = require('../src/ptyManager')

beforeEach(() => {
  spawnedInstances.length = 0
})

afterEach(() => {
  manager.closeAll()
})

describe('PTYManager.create()', () => {
  it('returns a session_id, cwd, and shell', () => {
    const info = manager.create()
    expect(info).toHaveProperty('session_id')
    expect(info).toHaveProperty('cwd')
    expect(info).toHaveProperty('shell')
    expect(typeof info.session_id).toBe('string')
    expect(info.session_id).toHaveLength(36) // UUID
  })

  it('increments the session count', () => {
    expect(manager.count()).toBe(0)
    manager.create()
    expect(manager.count()).toBe(1)
    manager.create()
    expect(manager.count()).toBe(2)
  })
})

describe('PTYManager.has()', () => {
  it('returns true for existing sessions', () => {
    const { session_id } = manager.create()
    expect(manager.has(session_id)).toBe(true)
  })

  it('returns false for unknown sessions', () => {
    expect(manager.has('nonexistent-id')).toBe(false)
  })
})

describe('PTYManager.write()', () => {
  it('throws for unknown session', () => {
    expect(() => manager.write('bad-id', 'hello')).toThrow()
  })
})

describe('PTYManager.resize()', () => {
  it('throws for unknown session', () => {
    expect(() => manager.resize('bad-id', 100, 40)).toThrow()
  })
})

describe('PTYManager.close()', () => {
  it('removes the session', () => {
    const { session_id } = manager.create()
    manager.close(session_id)
    expect(manager.has(session_id)).toBe(false)
    expect(manager.count()).toBe(0)
  })

  it('is idempotent for unknown sessions', () => {
    expect(() => manager.close('unknown-id')).not.toThrow()
  })
})

describe('PTYManager.closeAll()', () => {
  it('removes all sessions', () => {
    manager.create()
    manager.create()
    manager.create()
    manager.closeAll()
    expect(manager.count()).toBe(0)
  })
})

describe('PTYManager.write() with valid session', () => {
  it('forwards data to the PTY process', () => {
    const { session_id } = manager.create()
    const mockPty = spawnedInstances[spawnedInstances.length - 1]
    manager.write(session_id, 'ls -la\n')
    expect(mockPty.written).toContain('ls -la\n')
  })

  it('updates lastActivity timestamp', () => {
    const { session_id } = manager.create()
    const infoBefore = manager.getSessionInfo(session_id)
    const tsBefore = infoBefore.last_activity.getTime()
    manager.write(session_id, 'x')
    const infoAfter = manager.getSessionInfo(session_id)
    expect(infoAfter.last_activity.getTime()).toBeGreaterThanOrEqual(tsBefore)
  })
})

describe('PTYManager.resize() with valid session', () => {
  it('forwards resize to the PTY process', () => {
    const { session_id } = manager.create()
    const mockPty = spawnedInstances[spawnedInstances.length - 1]
    manager.resize(session_id, 160, 50)
    expect(mockPty.resized).toContainEqual({ cols: 160, rows: 50 })
  })
})

describe('PTYManager.getSessionInfo()', () => {
  it('returns created_at, last_activity and cwd', () => {
    const { session_id, cwd } = manager.create()
    const info = manager.getSessionInfo(session_id)
    expect(info).toHaveProperty('created_at')
    expect(info).toHaveProperty('last_activity')
    expect(info.cwd).toBe(cwd)
  })

  it('throws for unknown session', () => {
    expect(() => manager.getSessionInfo('bad-id')).toThrow()
  })
})

describe('PTYManager.onData()', () => {
  it('calls the callback when PTY emits data', () => {
    const { session_id } = manager.create()
    const received = []
    manager.onData(session_id, (d) => received.push(d))
    const mockPty = spawnedInstances[spawnedInstances.length - 1]
    mockPty._emitData('hello world')
    expect(received).toEqual(['hello world'])
  })

  it('throws for unknown session', () => {
    expect(() => manager.onData('bad-id', () => {})).toThrow()
  })
})

describe('PTYManager.onExit()', () => {
  it('calls the callback when PTY process exits', () => {
    const { session_id } = manager.create()
    let exitCode = null
    manager.onExit(session_id, (code) => { exitCode = code })
    const mockPty = spawnedInstances[spawnedInstances.length - 1]
    mockPty._emitExit(0, 0)
    expect(exitCode).toBe(0)
    // Session should be cleaned up after exit
    expect(manager.has(session_id)).toBe(false)
  })

  it('throws for unknown session', () => {
    expect(() => manager.onExit('bad-id', () => {})).toThrow()
  })
})
