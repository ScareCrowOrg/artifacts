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
}

export const CELL_FACTORY_KEY: InjectionKey<CellFactory> = Symbol('cellFactory')
