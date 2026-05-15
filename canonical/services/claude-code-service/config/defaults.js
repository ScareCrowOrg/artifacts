/**
 * @file config/defaults.js
 * @description Default configuration values for Claude Code Service.
 * These values are used when environment variables are not set.
 */

'use strict'

module.exports = {
  PORT: 8000,
  LOG_LEVEL: 'INFO',

  // Redis L1 heartbeat defaults
  REDIS_L1_HOST: 'redis',
  REDIS_L1_PORT: 6380,
  REDIS_L1_DB: 0,
  REDIS_L1_PASSWORD: 'scarerunner',
  HEARTBEAT_INTERVAL: 20,
  HEARTBEAT_TTL: 60,

  // WebSocket defaults
  WS_PATH: '/ws',

  // Claude Code defaults
  CLAUDE_HOME: '/app/claude-home',
}
