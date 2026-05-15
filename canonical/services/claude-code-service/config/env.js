/**
 * @file config/env.js
 * @description Load and validate environment variables, merging with defaults.
 * Reads from process.env (populated by dotenv in server.js).
 */

'use strict'

const defaults = require('./defaults')

function envInt(key, defaultValue) {
  const val = process.env[key]
  if (val === undefined || val === null) return defaultValue
  const trimmed = val.trim()
  if (trimmed === '') return defaultValue
  const parsed = parseInt(trimmed, 10)
  return isNaN(parsed) ? defaultValue : parsed
}

function envStr(key, defaultValue) {
  const val = process.env[key]
  if (val === undefined || val === null) return defaultValue
  const trimmed = val.trim()
  if (trimmed === '') return defaultValue
  return trimmed
}

const config = {
  PORT: envInt('PORT', defaults.PORT),
  LOG_LEVEL: envStr('LOG_LEVEL', defaults.LOG_LEVEL),

  REDIS_L1_HOST: envStr('REDIS_L1_HOST', defaults.REDIS_L1_HOST),
  REDIS_L1_PORT: envInt('REDIS_L1_PORT', defaults.REDIS_L1_PORT),
  REDIS_L1_DB: envInt('REDIS_L1_DB', defaults.REDIS_L1_DB),
  REDIS_L1_PASSWORD: envStr('REDIS_L1_PASSWORD', defaults.REDIS_L1_PASSWORD),
  HEARTBEAT_INTERVAL: envInt('HEARTBEAT_INTERVAL', defaults.HEARTBEAT_INTERVAL),
  HEARTBEAT_TTL: envInt('HEARTBEAT_TTL', defaults.HEARTBEAT_TTL),

  WS_PATH: envStr('WS_PATH', defaults.WS_PATH),

  CLAUDE_HOME: envStr('CLAUDE_HOME', defaults.CLAUDE_HOME),
}

module.exports = config
