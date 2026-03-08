/**
 * @file RedisExplorerCell.ts
 * @description Redis Explorer Cell - Interactive exploration and management of Redis keys
 *
 * Implements BaseCell interface for headless execution and composition.
 * Primary use case: UI-driven interactive exploration, but supports programmatic access.
 *
 * Features:
 * - Scan Redis keys by prefix with hierarchical navigation
 * - Inspect key values and metadata (type, TTL, size)
 * - Delete keys or key patterns
 * - Show Redis server info (version, memory, key count)
 */

import type { BaseCell, CellResult, CellMetadata, ValidationError, EnvironmentConfig } from '@/types/BaseCell'

/**
 * Input schema for Redis Explorer
 */
export interface RedisExplorerInput {
  /** Current prefix for exploration (empty for root) */
  current_prefix?: string

  /** Delimiter for hierarchical navigation */
  delimiter?: string

  /** Maximum depth for key scanning */
  max_depth?: number

  /** Action to perform: 'info', 'scan', 'get', 'delete' */
  action?: 'info' | 'scan' | 'get' | 'delete'

  /** Key to inspect (for 'get' action) */
  key?: string

  /** Pattern for deletion (for 'delete' action) */
  delete_pattern?: string

  /** Confirm deletion (for 'delete' action) */
  confirm_delete?: boolean
}

/**
 * Output schema for Redis Explorer results
 */
export interface RedisExplorerOutput {
  success: boolean
  action?: string

  // For 'info' action
  redis_info?: {
    version: string
    used_memory: string
    total_keys: number
    connected_clients: number
    uptime_seconds: number
  }

  // For 'scan' action
  scan_result?: {
    prefix: string
    delimiter: string
    nodes: string[]
    keys: string[]
    total_scanned: number
  }

  // For 'get' action
  key_value?: {
    key: string
    type: string
    value: any
    ttl: number
    size: number | null
  }

  // For 'delete' action
  delete_result?: {
    prefix: string
    keys_found: number
    keys_deleted: number
    sample_keys: string[]
  }

  message?: string
  error?: string
}

/**
 * Redis Explorer Cell
 *
 * Interactive cell for exploring and managing Redis data structures.
 * Supports both UI-driven exploration and programmatic access via BaseCell interface.
 */
export class RedisExplorerCell implements BaseCell {
  /**
   * Execute Redis Explorer operations
   *
   * Supports multiple actions:
   * - 'info': Get Redis server information
   * - 'scan': Scan keys at a prefix level
   * - 'get': Inspect a specific key
   * - 'delete': Delete keys matching a pattern
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const typedInput: RedisExplorerInput = input
      const action = typedInput.action || 'info'

      let output: RedisExplorerOutput = {
        success: false,
        action,
        message: ''
      }

      switch (action) {
        case 'info':
          output = await this.executeInfo()
          break

        case 'scan':
          output = await this.executeScan(typedInput)
          break

        case 'get':
          output = await this.executeGet(typedInput)
          break

        case 'delete':
          output = await this.executeDelete(typedInput)
          break

        default:
          throw new Error(`Unknown action: ${action}`)
      }

      return {
        success: output.success,
        output,
        execution_time: performance.now() - startTime
      }
    } catch (error) {
      return {
        success: false,
        output: {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
          message: 'Failed to execute Redis Explorer action'
        },
        execution_time: performance.now() - startTime,
        error: error instanceof Error ? error.message : 'Unknown error'
      }
    }
  }

  /**
   * Describe the cell's capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'redis-explorer',
      name: 'Redis Explorer',
      version: '1.0.0',
      description: 'Interactive exploration and management of Redis keys. Navigate hierarchical key structures, inspect values, and perform bulk operations.',

      inputs: {
        current_prefix: {
          type: 'string',
          description: 'Current prefix for hierarchical navigation',
          required: false,
          default: ''
        },
        delimiter: {
          type: 'string',
          description: 'Delimiter for hierarchical key grouping (default: ":")',
          required: false,
          default: ':'
        },
        max_depth: {
          type: 'integer',
          description: 'Maximum depth for key scanning',
          required: false,
          default: 1
        },
        action: {
          type: 'string',
          enum: ['info', 'scan', 'get', 'delete'],
          description: 'Action to perform',
          required: false,
          default: 'info'
        },
        key: {
          type: 'string',
          description: 'Key to inspect (required for "get" action)',
          required: false
        },
        delete_pattern: {
          type: 'string',
          description: 'Pattern for bulk deletion (required for "delete" action)',
          required: false
        },
        confirm_delete: {
          type: 'boolean',
          description: 'Confirm deletion (required for "delete" action)',
          required: false,
          default: false
        }
      },

      outputs: {
        success: {
          type: 'boolean',
          description: 'Whether the action succeeded'
        },
        action: {
          type: 'string',
          description: 'The action that was performed'
        },
        redis_info: {
          type: 'object',
          description: 'Redis server information (for "info" action)'
        },
        scan_result: {
          type: 'object',
          description: 'Scanned keys and branches (for "scan" action)'
        },
        key_value: {
          type: 'object',
          description: 'Key metadata and value (for "get" action)'
        },
        delete_result: {
          type: 'object',
          description: 'Deletion summary (for "delete" action)'
        },
        message: {
          type: 'string',
          description: 'Human-readable result message'
        },
        error: {
          type: 'string',
          description: 'Error message if action failed'
        }
      },

      tags: ['redis', 'database', 'exploration', 'management', 'ui-driven', 'headless-capable'],
      estimated_duration_seconds: 2
    }
  }

  /**
   * Validate input before execution
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    const typedInput: RedisExplorerInput = input

    // Validate action
    if (typedInput.action) {
      const validActions = ['info', 'scan', 'get', 'delete']
      if (!validActions.includes(typedInput.action)) {
        errors.push({
          field: 'action',
          message: `Invalid action. Must be one of: ${validActions.join(', ')}`
        })
      }
    }

    // Validate action-specific requirements
    if (typedInput.action === 'get' && !typedInput.key) {
      errors.push({
        field: 'key',
        message: 'Key is required for "get" action'
      })
    }

    if (typedInput.action === 'delete' && !typedInput.delete_pattern) {
      errors.push({
        field: 'delete_pattern',
        message: 'Pattern is required for "delete" action'
      })
    }

    // Validate numeric fields
    if (typedInput.max_depth !== undefined && typeof typedInput.max_depth !== 'number') {
      errors.push({
        field: 'max_depth',
        message: 'max_depth must be a number'
      })
    }

    if (typedInput.delimiter !== undefined && typeof typedInput.delimiter !== 'string') {
      errors.push({
        field: 'delimiter',
        message: 'delimiter must be a string'
      })
    }

    return errors
  }

  /**
   * Optional: Initialize resources
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    // No special initialization needed
    // Redis connection is handled by backend API
  }

  /**
   * Optional: Cleanup resources
   */
  async teardown(): Promise<void> {
    // No cleanup needed
  }

  /**
   * Optional: Health check
   */
  async health_check() {
    try {
      // Try a simple info call to verify Redis connectivity
      const response = await fetch('/api/redis-explorer/info', {
        headers: { 'Content-Type': 'application/json' }
      })

      return {
        status: response.ok ? 'healthy' : 'unavailable',
        can_execute: response.ok,
        reason: response.ok ? undefined : 'Redis server not responding'
      }
    } catch (error) {
      return {
        status: 'unavailable',
        can_execute: false,
        reason: 'Cannot reach Redis server'
      }
    }
  }

  // ===== PRIVATE HELPERS =====

  /**
   * Execute 'info' action - Get Redis server information
   */
  private async executeInfo(): Promise<RedisExplorerOutput> {
    try {
      const response = await fetch('/api/redis-explorer/info', {
        headers: { 'Content-Type': 'application/json' }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch Redis info')
      }

      const redisInfo = await response.json()

      return {
        success: true,
        action: 'info',
        redis_info: redisInfo,
        message: `Redis ${redisInfo.version} - ${redisInfo.total_keys} keys`
      }
    } catch (error) {
      return {
        success: false,
        action: 'info',
        error: error instanceof Error ? error.message : 'Unknown error',
        message: 'Failed to get Redis info'
      }
    }
  }

  /**
   * Execute 'scan' action - Scan keys at a prefix
   */
  private async executeScan(input: RedisExplorerInput): Promise<RedisExplorerOutput> {
    try {
      const response = await fetch('/api/redis-explorer/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prefix: input.current_prefix || '',
          delimiter: input.delimiter || ':',
          max_depth: input.max_depth || 1
        })
      })

      if (!response.ok) {
        throw new Error('Failed to scan Redis keys')
      }

      const scanResult = await response.json()

      return {
        success: true,
        action: 'scan',
        scan_result: scanResult,
        message: `Found ${scanResult.nodes.length} branches and ${scanResult.keys.length} keys`
      }
    } catch (error) {
      return {
        success: false,
        action: 'scan',
        error: error instanceof Error ? error.message : 'Unknown error',
        message: 'Failed to scan keys'
      }
    }
  }

  /**
   * Execute 'get' action - Inspect a specific key
   */
  private async executeGet(input: RedisExplorerInput): Promise<RedisExplorerOutput> {
    try {
      if (!input.key) {
        throw new Error('Key is required for "get" action')
      }

      const response = await fetch(`/api/redis-explorer/key/${encodeURIComponent(input.key)}`, {
        headers: { 'Content-Type': 'application/json' }
      })

      if (!response.ok) {
        throw new Error('Failed to load key value')
      }

      const keyValue = await response.json()

      return {
        success: true,
        action: 'get',
        key_value: keyValue,
        message: `Key type: ${keyValue.type}, Size: ${keyValue.size || 'N/A'} bytes`
      }
    } catch (error) {
      return {
        success: false,
        action: 'get',
        error: error instanceof Error ? error.message : 'Unknown error',
        message: 'Failed to get key value'
      }
    }
  }

  /**
   * Execute 'delete' action - Delete keys matching a pattern
   */
  private async executeDelete(input: RedisExplorerInput): Promise<RedisExplorerOutput> {
    try {
      if (!input.delete_pattern) {
        throw new Error('Pattern is required for "delete" action')
      }

      if (!input.confirm_delete) {
        throw new Error('Must confirm deletion (set confirm_delete to true)')
      }

      const response = await fetch('/api/redis-explorer/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prefix: input.delete_pattern,
          dry_run: false,
          confirm: true
        })
      })

      if (!response.ok) {
        throw new Error('Failed to delete keys')
      }

      const deleteResult = await response.json()

      return {
        success: true,
        action: 'delete',
        delete_result: deleteResult,
        message: `Deleted ${deleteResult.keys_deleted} key(s)`
      }
    } catch (error) {
      return {
        success: false,
        action: 'delete',
        error: error instanceof Error ? error.message : 'Unknown error',
        message: 'Failed to delete keys'
      }
    }
  }
}
