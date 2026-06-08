/**
 * @file LogToggleCell.ts
 * @description LogToggleCell - BaseCell implementation for temporarily enabling/disabling
 * log namespaces during a session for debugging and analysis.
 *
 * Pure frontend implementation — communicates with backend API for namespace discovery
 * and applies DEBUG patterns via the runtime logger system.
 * Settings are session-based and don't persist after restart.
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult } from '@/types/BaseCell'
import { setDebugPattern, getDebugPatternValue, getRegisteredNamespaces } from '@/utils/logger'
import apiService from '@/services/apiService'

/**
 * Input interface for LogToggleCell execution
 */
export interface LogToggleInput {
  /** List of namespace patterns to enable (e.g., ['auth:*', 'api', 'store']) */
  enabled_namespaces?: string[]

  /** Raw DEBUG pattern string (overrides enabled_namespaces if set) */
  debug_pattern?: string

  /** Whether to enable all namespaces */
  enable_all?: boolean

  /** Whether to disable all namespaces */
  disable_all?: boolean
}

/**
 * Output interface for LogToggleCell execution
 */
export interface LogToggleOutput {
  /** List of currently enabled namespaces */
  enabled_namespaces: string[]

  /** The applied DEBUG pattern string */
  applied_pattern: string

  /** Total available namespaces count */
  total_available: number

  /** Whether any namespaces are enabled */
  has_active: boolean
}

/**
 * LogToggleCell - Session-based log namespace toggling
 *
 * Provides programmatic control over runtime DEBUG patterns.
 * Can be used headless (via execute) or with View.vue for interactive use.
 *
 * Features:
 * - Enable/disable individual namespaces
 * - Enable/disable all namespaces
 * - Apply arbitrary DEBUG pattern strings
 * - Fallback namespace list when backend is unreachable
 * - Session-only — no persistence across restarts
 */
export class LogToggleCell extends BaseCell {
  private _isSetup: boolean = false
  private _knownNamespaces: string[] = []
  private _namespacesLoaded: boolean = false

  /**
   * Execute log toggle operations
   *
   * Applies the requested namespace changes to the runtime logger.
   * Can operate headless without a View component.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      // Validate input
      const errors = this.validate(input)
      if (errors.length > 0) {
        return {
          success: false,
          output: { errors },
          execution_time: performance.now() - startTime,
          error: 'Validation failed'
        }
      }

      // Resolve namespaces
      let enabledNamespaces: string[] = []
      const { enabled_namespaces, debug_pattern, enable_all, disable_all } = input as LogToggleInput

      // Load available namespaces if not already loaded
      if (!this._namespacesLoaded) {
        await this._loadNamespaces()
      }

      if (disable_all) {
        // Disable all — empty pattern
        setDebugPattern('')
        enabledNamespaces = []
      } else if (enable_all) {
        // Enable all — wildcard
        setDebugPattern('*')
        enabledNamespaces = [...this._knownNamespaces]
      } else if (debug_pattern !== undefined && debug_pattern !== null) {
        // Apply raw pattern string
        setDebugPattern(debug_pattern)
        enabledNamespaces = debug_pattern
          .split(',')
          .map(ns => ns.trim())
          .filter(Boolean)
      } else if (enabled_namespaces && enabled_namespaces.length > 0) {
        // Apply specific namespaces
        const pattern = enabled_namespaces.join(',')
        setDebugPattern(pattern)
        enabledNamespaces = enabled_namespaces
      } else {
        // No change — return current state
        const currentPattern = getDebugPatternValue()
        enabledNamespaces = currentPattern
          ? currentPattern.split(',').map(ns => ns.trim()).filter(Boolean)
          : []
      }

      const output: LogToggleOutput = {
        enabled_namespaces: enabledNamespaces,
        applied_pattern: enabledNamespaces.length === this._knownNamespaces.length && this._knownNamespaces.length > 0
          ? '*'
          : enabledNamespaces.join(','),
        total_available: this._knownNamespaces.length,
        has_active: enabledNamespaces.length > 0
      }

      return {
        success: true,
        output,
        execution_time: performance.now() - startTime,
        execution_steps: ['validate', 'load-namespaces', 'apply-pattern'],
        metadata: {
          action: enable_all ? 'enable_all' : disable_all ? 'disable_all' : debug_pattern ? 'apply_pattern' : enabled_namespaces ? 'apply_namespaces' : 'status_check',
          namespace_count: enabledNamespaces.length,
          total_available: this._knownNamespaces.length
        }
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Log toggle execution failed'
      }
    }
  }

  /**
   * Describe log toggle cell capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'log-toggle-cell',
      name: 'Log Toggle Cell',
      version: '1.0.0',
      description: 'Temporarily enable/disable specific log namespaces during a session for debugging and analysis',
      inputs: {
        enabled_namespaces: {
          type: 'array',
          description: 'List of namespace patterns to enable',
          items: { type: 'string' },
          required: false
        },
        debug_pattern: {
          type: 'string',
          description: 'Raw DEBUG pattern string (overrides enabled_namespaces)',
          required: false
        },
        enable_all: {
          type: 'boolean',
          description: 'Enable all available namespaces',
          required: false
        },
        disable_all: {
          type: 'boolean',
          description: 'Disable all namespaces',
          required: false
        }
      },
      outputs: {
        enabled_namespaces: {
          type: 'array',
          description: 'List of currently enabled namespaces'
        },
        applied_pattern: {
          type: 'string',
          description: 'The applied DEBUG pattern string'
        },
        total_available: {
          type: 'number',
          description: 'Total available namespaces count'
        },
        has_active: {
          type: 'boolean',
          description: 'Whether any namespaces are enabled'
        }
      },
      tags: ['logging', 'debug', 'utility', 'monitoring'],
      estimated_duration_seconds: 0.5,
      required_resources: []
    }
  }

  /**
   * Validate log toggle input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    // No input means status check — always valid
    if (!input || Object.keys(input).length === 0) {
      return errors
    }

    // enabled_namespaces must be an array of strings
    if (input.enabled_namespaces !== undefined) {
      if (!Array.isArray(input.enabled_namespaces)) {
        errors.push({ field: 'enabled_namespaces', message: 'Must be an array of strings' })
      } else {
        for (const ns of input.enabled_namespaces) {
          if (typeof ns !== 'string') {
            errors.push({ field: 'enabled_namespaces', message: 'Each namespace must be a string' })
            break
          }
        }
      }
    }

    // debug_pattern must be a string
    if (input.debug_pattern !== undefined && typeof input.debug_pattern !== 'string') {
      errors.push({ field: 'debug_pattern', message: 'Must be a string' })
    }

    // enable_all must be boolean
    if (input.enable_all !== undefined && typeof input.enable_all !== 'boolean') {
      errors.push({ field: 'enable_all', message: 'Must be a boolean' })
    }

    // disable_all must be boolean
    if (input.disable_all !== undefined && typeof input.disable_all !== 'boolean') {
      errors.push({ field: 'disable_all', message: 'Must be a boolean' })
    }

    return errors
  }

  /**
   * Setup — load known namespaces
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    await this._loadNamespaces()
    this._isSetup = true
  }

  /**
   * Teardown — release resources
   */
  async teardown(): Promise<void> {
    this._isSetup = false
    this._knownNamespaces = []
    this._namespacesLoaded = false
  }

  /**
   * Health check — verify logger system is accessible
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      // Quick check: can we read registered namespaces?
      const registered = getRegisteredNamespaces()
      return {
        status: 'healthy',
        can_execute: true
      }
    } catch {
      return {
        status: 'degraded',
        can_execute: true,
        reason: 'Logger system partially available — using fallback namespace list'
      }
    }
  }

  /**
   * Get serializable state
   */
  getState(): Record<string, any> {
    const currentPattern = getDebugPatternValue()
    return {
      enabled_namespaces: currentPattern
        ? currentPattern.split(',').map(ns => ns.trim()).filter(Boolean)
        : [],
      debug_pattern: currentPattern || ''
    }
  }

  /**
   * Restore state from persisted data
   */
  setState(state: Record<string, any>): void {
    if (state?.debug_pattern) {
      setDebugPattern(state.debug_pattern)
    } else if (state?.enabled_namespaces?.length) {
      setDebugPattern(state.enabled_namespaces.join(','))
    }
  }

  /**
   * Load available namespaces from backend API with fallback
   */
  private async _loadNamespaces(): Promise<void> {
    if (this._namespacesLoaded) return

    try {
      const response = await apiService.fetch('/api/logs/namespaces?discover=true', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
      })

      if (response.ok) {
        const namespaces = await response.json()
        this._knownNamespaces = Array.isArray(namespaces) ? namespaces : []
      } else {
        this._fallbackNamespaces()
      }
    } catch {
      this._fallbackNamespaces()
    }

    this._namespacesLoaded = true
  }

  /**
   * Fallback to registered + default namespaces when backend is unreachable
   */
  private _fallbackNamespaces(): void {
    const registered = getRegisteredNamespaces()
    const defaultNamespaces = [
      'app', 'auth', 'api', 'store', 'router',
      'debug', 'component', 'websocket', 'extension'
    ]
    this._knownNamespaces = [...new Set([...registered, ...defaultNamespaces])].sort()
  }
}
