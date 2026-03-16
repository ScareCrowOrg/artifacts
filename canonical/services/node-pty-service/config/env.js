/**
 * @file config/env.js
 * @description Load and validate environment variables, merging with defaults.
 * Reads from process.env (populated by dotenv in server.js).
 */

'use strict'

const defaults = require('./defaults')

/**
 * Parse an integer env var with fallback to default value.
 * @param {string} key - Environment variable name
 * @param {number} defaultValue - Fallback value
 * @returns {number}
 */
function envInt(key, defaultValue) {
  const val = process.env[key]
  if (val === undefined || val === null) return defaultValue
  const trimmed = val.trim()
  if (trimmed === '') return defaultValue
  const parsed = parseInt(trimmed, 10)
  return isNaN(parsed) ? defaultValue : parsed
}

/**
 * Parse a string env var with fallback to default value.
 * @param {string} key - Environment variable name
 * @param {string} defaultValue - Fallback value
 * @returns {string}
 */
function envStr(key, defaultValue) {
  const val = process.env[key]
  if (val === undefined || val === null) return defaultValue
  const trimmed = val.trim()
  if (trimmed === '') return defaultValue
  return trimmed
}

const config = {
  PORT: envInt('PORT', defaults.PORT),
  SESSION_TIMEOUT: envInt('SESSION_TIMEOUT', defaults.SESSION_TIMEOUT),
  LOG_LEVEL: envStr('LOG_LEVEL', defaults.LOG_LEVEL),
  ARTIFACTS_PATH: envStr('ARTIFACTS_PATH', defaults.ARTIFACTS_PATH),
  SHELL: envStr('SHELL', defaults.SHELL),
  MAX_SESSIONS: envInt('MAX_SESSIONS', defaults.MAX_SESSIONS),

  REDIS_L1_HOST: envStr('REDIS_L1_HOST', defaults.REDIS_L1_HOST),
  REDIS_L1_PORT: envInt('REDIS_L1_PORT', defaults.REDIS_L1_PORT),
  REDIS_L1_DB: envInt('REDIS_L1_DB', defaults.REDIS_L1_DB),
  REDIS_L1_PASSWORD: envStr('REDIS_L1_PASSWORD', defaults.REDIS_L1_PASSWORD),
  HEARTBEAT_INTERVAL: envInt('HEARTBEAT_INTERVAL', defaults.HEARTBEAT_INTERVAL),
  HEARTBEAT_TTL: envInt('HEARTBEAT_TTL', defaults.HEARTBEAT_TTL),

  WS_PATH: envStr('WS_PATH', defaults.WS_PATH),
  WS_PING_INTERVAL: envInt('WS_PING_INTERVAL', defaults.WS_PING_INTERVAL),
  WS_PING_TIMEOUT: envInt('WS_PING_TIMEOUT', defaults.WS_PING_TIMEOUT),

  PTY_COLS: envInt('PTY_COLS', defaults.PTY_COLS),
  PTY_ROWS: envInt('PTY_ROWS', defaults.PTY_ROWS),
}

module.exports = config
