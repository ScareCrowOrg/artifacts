/**
 * @file config/defaults.js
 * @description Default configuration values for Node-PTY Service.
 * These values are used when environment variables are not set.
 */

'use strict'

module.exports = {
  PORT: 8000,
  SESSION_TIMEOUT: 3600,     // seconds before idle session is closed
  LOG_LEVEL: 'INFO',          // DEBUG | INFO | ERROR
  ARTIFACTS_PATH: '/app/artifacts',
  SHELL: '/bin/bash',
  MAX_SESSIONS: 50,           // maximum concurrent PTY sessions

  // Redis L1 heartbeat defaults
  REDIS_L1_HOST: 'redis',
  REDIS_L1_PORT: 6380,
  REDIS_L1_DB: 0,
  REDIS_L1_PASSWORD: 'scarerunner',
  HEARTBEAT_INTERVAL: 20,    // seconds between heartbeat refreshes
  HEARTBEAT_TTL: 60,         // seconds before key expires (3× interval)

  // WebSocket defaults
  WS_PATH: '/ws',
  WS_PING_INTERVAL: 30000,   // ms between pings to detect dead connections
  WS_PING_TIMEOUT: 5000,     // ms to wait for pong before closing

  // PTY defaults (xterm.js compatible)
  PTY_COLS: 80,
  PTY_ROWS: 24,
}
