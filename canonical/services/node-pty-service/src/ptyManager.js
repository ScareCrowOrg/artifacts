/**
 * @file src/ptyManager.js
 * @description PTY session manager using node-pty.
 *
 * Manages multiple concurrent pseudo-terminal sessions.
 * Each session is identified by a UUID and maps to a spawned shell process.
 *
 * Session lifecycle:
 *   create → data events → resize → close (explicit or timeout)
 */

'use strict'

const pty = require('node-pty')
const { v4: uuidv4 } = require('uuid')
const config = require('../config/env')

/**
 * @typedef {Object} Session
 * @property {string} id - Session UUID
 * @property {import('node-pty').IPty} pty - PTY process
 * @property {Date} createdAt - Session creation time
 * @property {Date} lastActivity - Last input/output time
 * @property {string} cwd - Current working directory
 * @property {NodeJS.Timeout|null} timeoutTimer - Idle timeout handle
 */

class PTYManager {
  constructor() {
    /** @type {Map<string, Session>} */
    this._sessions = new Map()
    this._log = this._buildLogger()
  }

  /**
   * Create a new PTY session.
   *
   * @param {object} [opts]
   * @param {number} [opts.cols] - Terminal columns
   * @param {number} [opts.rows] - Terminal rows
   * @param {string} [opts.cwd] - Initial working directory
   * @returns {{ session_id: string, cwd: string, shell: string }}
   */
  create(opts = {}) {
    const sessionId = uuidv4()
    const cols = opts.cols || config.PTY_COLS
    const rows = opts.rows || config.PTY_ROWS
    const cwd = opts.cwd || config.ARTIFACTS_PATH
    const shell = config.SHELL || '/bin/bash'

    const ptyProcess = pty.spawn(shell, [], {
      name: 'xterm-256color',
      cols,
      rows,
      cwd,
      env: {
        ...process.env,
        TERM: 'xterm-256color',
        HOME: process.env.HOME || '/root',
        USER: process.env.USER || 'root',
      },
    })

    const session = {
      id: sessionId,
      pty: ptyProcess,
      createdAt: new Date(),
      lastActivity: new Date(),
      cwd,
      timeoutTimer: null,
    }

    this._sessions.set(sessionId, session)
    this._scheduleTimeout(session)

    this._log('info', `Session created: ${sessionId} (shell=${shell}, cwd=${cwd})`)

    return { session_id: sessionId, cwd, shell }
  }

  /**
   * Attach a data listener to a session's PTY output.
   *
   * @param {string} sessionId
   * @param {(data: string) => void} callback
   * @returns {import('node-pty').IDisposable}
   */
  onData(sessionId, callback) {
    const session = this._getSession(sessionId)
    return session.pty.onData((data) => {
      session.lastActivity = new Date()
      this._rescheduleTimeout(session)
      callback(data)
    })
  }

  /**
   * Attach an exit listener to a session's PTY process.
   *
   * @param {string} sessionId
   * @param {(exitCode: number, signal: number) => void} callback
   * @returns {import('node-pty').IDisposable}
   */
  onExit(sessionId, callback) {
    const session = this._getSession(sessionId)
    return session.pty.onExit(({ exitCode, signal }) => {
      this._log('info', `Session ${sessionId} exited (code=${exitCode}, signal=${signal})`)
      this._cleanup(sessionId)
      callback(exitCode, signal)
    })
  }

  /**
   * Write input data to a PTY session.
   *
   * @param {string} sessionId
   * @param {string} data - Raw input (e.g., "ls -la\n")
   */
  write(sessionId, data) {
    const session = this._getSession(sessionId)
    session.lastActivity = new Date()
    this._rescheduleTimeout(session)
    session.pty.write(data)
  }

  /**
   * Resize a PTY session's terminal dimensions.
   *
   * @param {string} sessionId
   * @param {number} cols
   * @param {number} rows
   */
  resize(sessionId, cols, rows) {
    const session = this._getSession(sessionId)
    session.pty.resize(cols, rows)
    this._log('debug', `Session ${sessionId} resized to ${cols}x${rows}`)
  }

  /**
   * Return metadata for a session.
   *
   * @param {string} sessionId
   * @returns {{ created_at: Date, last_activity: Date, cwd: string }}
   */
  getSessionInfo(sessionId) {
    const session = this._getSession(sessionId)
    return {
      created_at: session.createdAt,
      last_activity: session.lastActivity,
      cwd: session.cwd,
    }
  }

  /**
   * Close a PTY session and release resources.
   *
   * @param {string} sessionId
   */
  close(sessionId) {
    if (!this._sessions.has(sessionId)) return
    const session = this._sessions.get(sessionId)
    this._cleanup(sessionId)
    try {
      session.pty.kill()
    } catch (err) {
      this._log('debug', `Session ${sessionId}: kill() failed (${err.message})`)
    }
    this._log('info', `Session ${sessionId} closed`)
  }

  /**
   * Check whether a session exists.
   *
   * @param {string} sessionId
   * @returns {boolean}
   */
  has(sessionId) {
    return this._sessions.has(sessionId)
  }

  /**
   * Return the number of active sessions.
   * @returns {number}
   */
  count() {
    return this._sessions.size
  }

  /**
   * Close all sessions (called on shutdown).
   */
  closeAll() {
    for (const sessionId of [...this._sessions.keys()]) {
      this.close(sessionId)
    }
  }

  // ─── Private helpers ──────────────────────────────────────────────────────

  _getSession(sessionId) {
    const session = this._sessions.get(sessionId)
    if (!session) throw new Error(`Session not found: ${sessionId}`)
    return session
  }

  _cleanup(sessionId) {
    const session = this._sessions.get(sessionId)
    if (!session) return
    if (session.timeoutTimer) {
      clearTimeout(session.timeoutTimer)
    }
    this._sessions.delete(sessionId)
  }

  _scheduleTimeout(session) {
    if (!config.SESSION_TIMEOUT || config.SESSION_TIMEOUT <= 0) return
    session.timeoutTimer = setTimeout(() => {
      this._log('info', `Session ${session.id} timed out (idle > ${config.SESSION_TIMEOUT}s)`)
      try {
        session.pty.kill()
      } catch (err) {
        this._log('debug', `Session ${session.id}: kill() on timeout failed (${err.message})`)
      }
      this._sessions.delete(session.id)
    }, config.SESSION_TIMEOUT * 1000)
    if (session.timeoutTimer.unref) session.timeoutTimer.unref()
  }

  _rescheduleTimeout(session) {
    if (session.timeoutTimer) clearTimeout(session.timeoutTimer)
    this._scheduleTimeout(session)
  }

  _buildLogger() {
    const level = (config.LOG_LEVEL || 'INFO').toUpperCase()
    return (msgLevel, message) => {
      if (level === 'ERROR' && msgLevel !== 'error') return
      if (level === 'INFO' && msgLevel === 'debug') return
      const ts = new Date().toISOString()
      console.log(`[${ts}] [PTYManager] [${msgLevel.toUpperCase()}] ${message}`)
    }
  }
}

module.exports = new PTYManager()
