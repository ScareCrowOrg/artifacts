/**
 * CellFactory — Provide/Inject Pattern for Child Cell Creation
 *
 * Allows child cells (e.g. file-manager-cell) to create new cells in the
 * workspace grid without importing cockpit-vue legacy stores.
 *
 * Usage:
 *   // In App.vue:
 *   import { CELL_FACTORY_KEY, cellFactory } from '#canonical/shared/cellFactory'
 *   provide(CELL_FACTORY_KEY, cellFactory)
 *
 *   // In child cell:
 *   import { CELL_FACTORY_KEY, type CellFactory } from '#canonical/shared/cellFactory'
 *   const cellFactory = inject(CELL_FACTORY_KEY)
 *   cellFactory?.addChildCell('file-editor-v2', { fileName, filePath })
 */

import type { InjectionKey } from 'vue'

export interface CellFactory {
  addChildCell(type: string, initialData?: Record<string, any>): Promise<string | undefined>
  closeCell(cellId: string): Promise<void>
}

export const CELL_FACTORY_KEY: InjectionKey<CellFactory> = Symbol('cellFactory')

/**
 * CellStateBridge — Provide/Inject Pattern for Cell State Sharing
 *
 * Allows View.vue to share content_ids with App.vue for persistence.
 * App.vue uses registered providers during save to capture the current
 * content reference state (relative_urls, content_ids) from the active View.vue.
 *
 * Usage:
 *   // In App.vue:
 *   import { CELL_STATE_BRIDGE_KEY, type CellStateBridge } from '#canonical/shared/cellFactory'
 *   provide(CELL_STATE_BRIDGE_KEY, { registerStateProvider, unregisterStateProvider })
 *
 *   // In View.vue:
 *   import { CELL_STATE_BRIDGE_KEY, type CellStateBridge } from '#canonical/shared/cellFactory'
 *   const bridge = inject(CELL_STATE_BRIDGE_KEY)
 *   bridge?.registerStateProvider(cellId, () => ({ mesh_content_id: ... }))
 */
export interface CellStateBridge {
  registerStateProvider(cellId: string, provider: () => Record<string, any>): void
  unregisterStateProvider(cellId: string): void
}

export const CELL_STATE_BRIDGE_KEY: InjectionKey<CellStateBridge> = Symbol('cellStateBridge')
