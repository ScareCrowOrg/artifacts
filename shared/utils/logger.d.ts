/**
 * TypeScript declarations for logger.js
 * Provides type safety for the logging utility
 */

/**
 * Log levels enum
 */
export const LogLevel: {
  readonly DEBUG: 'debug'
  readonly INFO: 'info'
  readonly SUCCESS: 'success'
  readonly WARN: 'warn'
  readonly ERROR: 'error'
}

/**
 * Log entry structure
 */
export interface LogEntry {
  timestamp: string
  level: string
  namespace: string
  message: string
  data?: any[]
}

/**
 * Logger interface returned by createLogger
 */
export interface Logger {
  /**
   * Log debug message
   * @param message - Debug message
   * @param args - Additional arguments
   */
  debug(message: string, ...args: any[]): void

  /**
   * Log info message
   * @param message - Info message
   * @param args - Additional arguments
   */
  info(message: string, ...args: any[]): void

  /**
   * Log warning message
   * @param message - Warning message
   * @param args - Additional arguments
   */
  warn(message: string, ...args: any[]): void

  /**
   * Log error message
   * @param message - Error message
   * @param args - Additional arguments
   */
  error(message: string, ...args: any[]): void

  /**
   * Log success message
   * @param message - Success message
   * @param args - Additional arguments
   */
  success(message: string, ...args: any[]): void

  /**
   * Check if this logger is enabled
   * @returns Whether logging is enabled for this logger's namespace
   */
  isEnabled(): boolean

  /**
   * Get the namespace of this logger
   * @returns The logger's namespace
   */
  getNamespace(): string
}

/**
 * Log collector for programmatic access to logs
 */
export interface LogCollector {
  logs: LogEntry[]
  maxSize: number
  enabled: boolean

  enable(): void
  disable(): void
  add(logEntry: LogEntry): void
  getAll(): LogEntry[]
  getByNamespace(namespace: string): LogEntry[]
  getByLevel(level: string): LogEntry[]
  clear(): void
  export(): {
    timestamp: string
    totalLogs: number
    logs: LogEntry[]
  }
}

/**
 * Create a namespaced logger
 * @param namespace - The namespace for this logger (e.g., 'auth', 'api', 'store:cells')
 * @returns Logger instance with debug, info, warn, error, success methods
 */
export function createLogger(namespace: string): Logger

/**
 * Get the global log collector
 * @returns The global log collector instance
 */
export function getLogCollector(): LogCollector

/**
 * Enable log collection
 */
export function enableLogCollection(): void

/**
 * Disable log collection
 */
export function disableLogCollection(): void

/**
 * Export all collected logs
 * @returns Exported log data
 */
export function exportLogs(): {
  timestamp: string
  totalLogs: number
  logs: LogEntry[]
}

/**
 * Clear all collected logs
 */
export function clearLogs(): void

/**
 * Set debug pattern for conditional logging
 * @param pattern - Debug pattern (e.g., 'auth:*', 'store:*')
 */
export function setDebugPattern(pattern: string): void

/**
 * Get current debug pattern value
 * @returns Current debug pattern
 */
export function getDebugPatternValue(): string

/**
 * Get all registered logger namespaces
 * @returns Array of registered namespaces
 */
export function getRegisteredNamespaces(): string[]

/**
 * Default logger with 'app' namespace
 */
declare const defaultLogger: Logger
export default defaultLogger
