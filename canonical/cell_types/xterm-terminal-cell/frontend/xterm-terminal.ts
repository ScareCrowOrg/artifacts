/**
 * @file frontend/xterm-terminal.ts
 * @description XtermTerminalCell – BaseCell implementation for the xterm-terminal-cell type.
 *
 * This is a UI-only cell. Execution is a no-op because the terminal renders
 * itself via a WebSocket connection established inside View.vue. The BaseCell
 * methods are still implemented to satisfy the mandatory interface and to
 * expose metadata useful for introspection and headless testing.
 */

import { BaseCell } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  HealthCheckResult,
} from '@/types/BaseCell'

/**
 * Input schema for XtermTerminalCell.execute()
 */
export interface XtermTerminalInput {
  /** WebSocket endpoint of the Node-PTY service */
  ws_url?: string
  /** Terminal columns */
  cols?: number
  /** Terminal rows */
  rows?: number
  /** Font size in pixels */
  font_size?: number
  /** Color theme */
  theme?: 'dark' | 'light'
}

/**
 * XtermTerminalCell – BaseCell implementation.
 *
 * Execute is intentionally a no-op: the real interaction happens in View.vue
 * via the usePTYConnection composable. This class satisfies the mandatory
 * BaseCell contract and provides metadata + validation.
 *
 * @example
 * ```typescript
 * const cell = new XtermTerminalCell()
 * const meta = await cell.describe()
 * console.log(meta.id) // 'xterm-terminal-cell'
 *
 * const errors = cell.validate({ ws_url: 'not-a-ws-url' })
 * // => [{ field: 'ws_url', message: '...' }]
 * ```
 */
export class XtermTerminalCell extends BaseCell {
  /**
   * Execute is a no-op for this UI-only cell.
   * The terminal session is managed by the View component via WebSocket.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    const errors = this.validate(input)
    if (errors.length > 0) {
      return {
        success: false,
        output: { errors },
        execution_time: performance.now() - startTime,
        error: 'Validation failed',
      }
    }

    return {
      success: true,
      output: {
        message: 'XtermTerminalCell is a UI-only cell. Connect View.vue to the Node-PTY service.',
        ws_url: input.ws_url || 'ws://node-pty-service:8000/ws',
      },
      execution_time: performance.now() - startTime,
      metadata: {
        cell_type: 'xterm-terminal-cell',
        ui_only: true,
      },
    }
  }

  /**
   * Describe cell capabilities and schema.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'xterm-terminal-cell',
      name: 'Terminal',
      version: '1.0.0',
      description:
        'Interactive terminal cell powered by xterm.js. Connects to the Node-PTY ' +
        'service over WebSocket for persistent shell sessions. UI-only: no backend execution.',
      inputs: {
        ws_url: {
          type: 'string',
          description: 'WebSocket endpoint of the Node-PTY service',
          required: false,
          default: 'ws://node-pty-service:8000/ws',
        },
        cols: {
          type: 'number',
          description: 'Terminal columns',
          required: false,
          default: 120,
        },
        rows: {
          type: 'number',
          description: 'Terminal rows',
          required: false,
          default: 40,
        },
        font_size: {
          type: 'number',
          description: 'Font size in pixels',
          required: false,
          default: 14,
        },
        theme: {
          type: 'string',
          description: 'Color theme: dark or light',
          required: false,
          default: 'dark',
          enum: ['dark', 'light'],
        },
      },
      outputs: {
        message: {
          type: 'string',
          description: 'Status message',
        },
        ws_url: {
          type: 'string',
          description: 'WebSocket URL in use',
        },
      },
      tags: ['terminal', 'pty', 'shell', 'websocket', 'xterm', 'infrastructure', 'ai-agents'],
      estimated_duration_seconds: 0,
      required_resources: ['node-pty-service'],
    }
  }

  /**
   * Validate cell input.
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (input.ws_url !== undefined && typeof input.ws_url === 'string') {
      const url = input.ws_url.trim()
      if (url !== '' && !url.startsWith('ws://') && !url.startsWith('wss://')) {
        errors.push({
          field: 'ws_url',
          message: 'ws_url must start with ws:// or wss://',
        })
      }
    }

    if (input.cols !== undefined) {
      const cols = Number(input.cols)
      if (isNaN(cols) || cols < 10 || cols > 500) {
        errors.push({ field: 'cols', message: 'cols must be between 10 and 500' })
      }
    }

    if (input.rows !== undefined) {
      const rows = Number(input.rows)
      if (isNaN(rows) || rows < 5 || rows > 200) {
        errors.push({ field: 'rows', message: 'rows must be between 5 and 200' })
      }
    }

    if (input.font_size !== undefined) {
      const size = Number(input.font_size)
      if (isNaN(size) || size < 8 || size > 32) {
        errors.push({ field: 'font_size', message: 'font_size must be between 8 and 32' })
      }
    }

    if (input.theme !== undefined && !['dark', 'light'].includes(input.theme)) {
      errors.push({ field: 'theme', message: 'theme must be "dark" or "light"' })
    }

    return errors
  }

  /**
   * Health check: always healthy (UI-only cell with no runtime dependencies).
   */
  async health_check(): Promise<HealthCheckResult> {
    return {
      healthy: true,
      message: 'XtermTerminalCell is always healthy (UI-only)',
    }
  }
}
