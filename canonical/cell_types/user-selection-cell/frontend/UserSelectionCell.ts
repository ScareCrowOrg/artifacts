/**
 * @file UserSelectionCell.ts
 * @description UserSelectionCell — ephemeral BaseCell for user selection via modal overlay.
 *
 * This cell is NOT instantiated by users directly (category: "ephemeral").
 * It is invoked programmatically by other cells (e.g. ArtifactsExplorerCell.allowArtifact())
 * via its show() method, which returns a Promise<SelectableUser | null>.
 *
 * Flow:
 * 1. Caller: `const user = await userCell.show({}, { mode: 'pick-one', title: '...' })`
 * 2. show() registers a Promise resolver via userSelectionStore.open()
 * 3. View.vue opens, loads users, and waits for user interaction
 * 4. User clicks a user → store.selectUser(user) → Promise resolves with user
 * 5. User clicks Cancel → store.cancel() → Promise resolves with null
 */

import { BaseCell } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  ShowConfig,
} from '@/types/BaseCell'
import { createLogger } from '@/utils/logger'
import { useUserSelectionStore } from './store'
import type { SelectableUser } from './store'

const log = createLogger('cell:user-selection')

export class UserSelectionCell extends BaseCell {
  /**
   * execute() — not the primary interface for this cell.
   * Returns a noop result since user-selection-cell is show()-driven.
   */
  async execute(_input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    log.debug('[UserSelectionCell] execute() called (noop — use show() instead)')
    return {
      success: true,
      output: { message: 'UserSelectionCell is invoked via show(), not execute().' },
      execution_time: performance.now() - startTime,
    }
  }

  /**
   * describe() — cell metadata for the discovery system.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'user-selection-cell',
      name: 'User Selection Cell',
      version: '1.0.0',
      description:
        'Ephemeral cell that opens a modal overlay for selecting a user. ' +
        'Returns Promise<SelectableUser | null> via show(). Admin-only.',
      inputs: {
        mode: {
          type: 'string',
          description: "Selection mode. Only 'pick-one' is supported.",
          required: false,
          default: 'pick-one',
        },
        title: {
          type: 'string',
          description: 'Title shown in the selection overlay.',
          required: false,
          default: 'Select a User',
        },
      },
      outputs: {
        user: {
          type: 'object',
          description: 'The selected user, or null if cancelled.',
        },
      },
      tags: ['user', 'selection', 'modal', 'ephemeral', 'admin'],
    }
  }

  /**
   * validate() — validates show() options.
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    if (input.mode && input.mode !== 'pick-one') {
      errors.push({
        field: 'mode',
        message: "Only 'pick-one' mode is currently supported.",
      })
    }
    return errors
  }

  /**
   * show() — OVERRIDDEN to open the user selection overlay.
   *
   * This is the primary interface of UserSelectionCell.
   * Returns a Promise that resolves with a SelectableUser (if selected)
   * or null (if cancelled).
   *
   * @param _data - Unused data payload (kept for BaseCell interface compatibility)
   * @param options - ShowConfig with optional `title` and `mode`
   * @returns Promise<SelectableUser | null>
   *
   * @example
   * ```typescript
   * const userCell = new UserSelectionCell()
   * const user = await userCell.show({}, { mode: 'pick-one', title: 'Select user for allowance' })
   * if (user) {
   *   console.log(`Selected: ${user.username}`)
   * }
   * ```
   */
  async show(
    _data: Record<string, any>,
    options: ShowConfig,
  ): Promise<SelectableUser | null> {
    const overlayTitle =
      typeof options?.title === 'string' ? options.title : 'Select a User'

    log.debug('[UserSelectionCell] show() called', { title: overlayTitle })

    const store = useUserSelectionStore()

    // Register pending fragment
    log.debug('[UserSelectionCell] Fragment: pending pick-user')

    return new Promise<SelectableUser | null>((resolve) => {
      store.open(overlayTitle, (user) => {
        // Register completed fragment
        log.debug('[UserSelectionCell] Fragment: completed pick-user', {
          selected: user ? user.username : null,
        })
        resolve(user)
      })
    })
  }
}

export default UserSelectionCell
