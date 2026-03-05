/**
 * Advanced Logging System for Vue.js
 * 
 * Features:
 * - Namespace/key-based log control
 * - Runtime configuration via localStorage
 * - Environment variable control via DEBUG
 * - Automatic removal in production builds
 * - Programmatic log collection
 * - Structured log format
 * - Dynamic re-evaluation of enabled namespaces
 * 
 * Usage:
 *   import { createLogger } from '@/utils/logger'
 *   const log = createLogger('auth')
 *   log.debug('User logged in', { userId: 123 })
 *   log.info('Session started')
 *   log.success('Operation completed successfully')
 *   log.warn('Session expiring soon')
 *   log.error('Login failed', error)
 * 
 * Environment Control:
 *   DEBUG=* - Enable all logs
 *   DEBUG=auth,api - Enable only 'auth' and 'api' namespaces
 *   DEBUG=auth:* - Enable all 'auth' sub-namespaces
 *   NODE_ENV=production - Automatically disables all logs
 * 
 * Runtime Control:
 *   import { setDebugPattern } from '@/utils/logger'
 *   setDebugPattern('auth,api') - Enable specific namespaces
 *   setDebugPattern('*') - Enable all namespaces
 *   setDebugPattern('') - Disable all namespaces (explicitly)
 *   setDebugPattern(null) - Reset to default behavior (DEV mode fallback)
 * 
 * @module utils/logger
 */

// Log levels
export const LogLevel = {
  DEBUG: 'debug',
  INFO: 'info',
  SUCCESS: 'success',
  WARN: 'warn',
  ERROR: 'error'
}

// Visual indicators
const SUCCESS_INDICATOR = '✓'

// Log collector - stores logs for programmatic access
class LogCollector {
  constructor(maxSize = 1000) {
    this.logs = []
    this.maxSize = maxSize
    this.enabled = false
  }

  enable() {
    this.enabled = true
  }

  disable() {
    this.enabled = false
  }

  add(logEntry) {
    if (!this.enabled) return
    
    this.logs.push(logEntry)
    
    // Circular buffer - remove oldest if exceeds max size
    if (this.logs.length > this.maxSize) {
      this.logs.shift()
    }
  }

  getAll() {
    return [...this.logs]
  }

  getByNamespace(namespace) {
    return this.logs.filter(log => log.namespace === namespace)
  }

  getByLevel(level) {
    return this.logs.filter(log => log.level === level)
  }

  clear() {
    this.logs = []
  }

  export() {
    return {
      timestamp: new Date().toISOString(),
      totalLogs: this.logs.length,
      logs: this.getAll()
    }
  }
}

// Global log collector instance
const globalCollector = new LogCollector()

// Global logger registry for tracking and introspection
const loggerRegistry = new Map()

/**
 * Get the current DEBUG pattern from runtime storage or environment
 * @returns {string} - Current DEBUG pattern
 */
function getDebugPattern() {
  // In production, always return empty
  if (import.meta.env.PROD) {
    return ''
  }

  // Check localStorage first (runtime configuration)
  try {
    const runtimeDebug = localStorage.getItem('DEBUG')
    if (runtimeDebug !== null) {
      return runtimeDebug
    }
  } catch (e) {
    // localStorage may not be available in some contexts
  }

  // Fall back to environment variables
  return import.meta.env.VITE_DEBUG || import.meta.env.DEBUG || ''
}

/**
 * Check if a namespace should be logged based on DEBUG pattern
 * @param {string} namespace - The namespace to check
 * @returns {boolean} - Whether logging is enabled for this namespace
 */
function isNamespaceEnabled(namespace) {
  // In production, disable all logging
  if (import.meta.env.PROD) {
    return false
  }

  // Get DEBUG pattern (runtime or environment)
  const debug = getDebugPattern()
  
  // Check for explicit disable marker
  if (debug === 'DISABLED') {
    return false
  }
  
  // If DEBUG is empty, check DEV mode
  if (!debug) {
    return import.meta.env.DEV
  }

  // If DEBUG is '*', enable all
  if (debug === '*') {
    return true
  }

  // Split DEBUG into individual patterns
  const patterns = debug.split(',').map(p => p.trim())

  // Check if namespace matches any pattern
  return patterns.some(pattern => {
    // Exact match
    if (pattern === namespace) {
      return true
    }

    // Wildcard match (e.g., 'auth:*' matches 'auth:login', 'auth:logout')
    if (pattern.endsWith(':*')) {
      const prefix = pattern.slice(0, -2)
      return namespace.startsWith(prefix + ':') || namespace === prefix
    }

    // Wildcard at start (e.g., '*:error' matches 'auth:error', 'api:error')
    if (pattern.startsWith('*:')) {
      const suffix = pattern.slice(2)
      return namespace.endsWith(':' + suffix)
    }

    return false
  })
}

/**
 * Create a namespaced logger
 * @param {string} namespace - The namespace for this logger (e.g., 'auth', 'api', 'store:cells')
 * @returns {Object} - Logger instance with debug, info, warn, error methods
 */
export function createLogger(namespace) {
  /**
   * Log a message
   * @param {string} level - Log level
   * @param {string} message - Log message
   * @param {...any} args - Additional arguments
   */
  function log(level, message, ...args) {
    // Check if namespace is enabled at log time (dynamic evaluation)
    if (!isNamespaceEnabled(namespace)) {
      return
    }

    // Create log entry
    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      namespace,
      message,
      data: args.length > 0 ? args : undefined
    }

    // Add to collector
    globalCollector.add(logEntry)

    // Format message with namespace prefix
    const prefix = `[${namespace}]`
    
    // Output to console based on level
    switch (level) {
      case LogLevel.DEBUG:
        console.log(prefix, message, ...args)
        break
      case LogLevel.INFO:
        console.info(prefix, message, ...args)
        break
      case LogLevel.SUCCESS:
        // Use console.log with a visual indicator for success
        console.log(`${SUCCESS_INDICATOR} ${prefix}`, message, ...args)
        break
      case LogLevel.WARN:
        console.warn(prefix, message, ...args)
        break
      case LogLevel.ERROR:
        console.error(prefix, message, ...args)
        break
    }
  }

  const logger = {
    /**
     * Log debug message
     * @param {string} message - Debug message
     * @param {...any} args - Additional arguments
     */
    debug(message, ...args) {
      log(LogLevel.DEBUG, message, ...args)
    },

    /**
     * Log info message
     * @param {string} message - Info message
     * @param {...any} args - Additional arguments
     */
    info(message, ...args) {
      log(LogLevel.INFO, message, ...args)
    },

    /**
     * Log warning message
     * @param {string} message - Warning message
     * @param {...any} args - Additional arguments
     */
    warn(message, ...args) {
      log(LogLevel.WARN, message, ...args)
    },

    /**
     * Log error message
     * @param {string} message - Error message
     * @param {...any} args - Additional arguments
     */
    error(message, ...args) {
      log(LogLevel.ERROR, message, ...args)
    },

    /**
     * Log success message
     * @param {string} message - Success message
     * @param {...any} args - Additional arguments
     */
    success(message, ...args) {
      log(LogLevel.SUCCESS, message, ...args)
    },

    /**
     * Check if this logger is enabled (dynamic evaluation)
     * @returns {boolean}
     */
    isEnabled() {
      return isNamespaceEnabled(namespace)
    },

    /**
     * Get the namespace of this logger
     * @returns {string}
     */
    getNamespace() {
      return namespace
    }
  }

  // Register logger for tracking
  // Note: Overwrites if same namespace registered multiple times
  // This is intentional - we track the most recently created instance
  loggerRegistry.set(namespace, logger)

  return logger
}

/**
 * Get the global log collector
 * @returns {LogCollector}
 */
export function getLogCollector() {
  return globalCollector
}

/**
 * Enable log collection
 */
export function enableLogCollection() {
  globalCollector.enable()
}

/**
 * Disable log collection
 */
export function disableLogCollection() {
  globalCollector.disable()
}

/**
 * Export all collected logs
 * @returns {Object} - Exported log data
 */
export function exportLogs() {
  return globalCollector.export()
}

/**
 * Clear all collected logs
 */
export function clearLogs() {
  globalCollector.clear()
}

/**
 * Update the DEBUG pattern at runtime
 * @param {string} pattern - New DEBUG pattern (e.g., 'auth,api', '*', '')
 *                          Empty string ('') explicitly disables all logs
 *                          null/undefined resets to default behavior
 */
export function setDebugPattern(pattern) {
  try {
    if (pattern === '') {
      // Empty string means explicitly disable all logs
      localStorage.setItem('DEBUG', 'DISABLED')
    } else if (pattern) {
      // Non-empty pattern: store it
      localStorage.setItem('DEBUG', pattern)
    } else {
      // null or undefined: remove configuration (use defaults)
      localStorage.removeItem('DEBUG')
    }
  } catch (e) {
    console.error('Failed to update DEBUG pattern in localStorage:', e)
  }
}

/**
 * Get the current DEBUG pattern
 * @returns {string} - Current DEBUG pattern
 */
export function getDebugPatternValue() {
  return getDebugPattern()
}

/**
 * Get all registered logger namespaces
 * @returns {string[]} - Array of registered namespaces
 */
export function getRegisteredNamespaces() {
  return Array.from(loggerRegistry.keys())
}

/**
 * Get status of all registered loggers
 * @returns {Object[]} - Array of logger status objects
 */
export function getLoggerStatus() {
  return Array.from(loggerRegistry.entries()).map(([namespace, logger]) => ({
    namespace,
    enabled: logger.isEnabled()
  }))
}

// For backward compatibility, provide a default logger
export default createLogger('app')
