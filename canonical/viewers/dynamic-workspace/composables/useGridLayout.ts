/**
 * composables/useGridLayout.ts
 *
 * Grid state management for DynamicWorkspace v2.
 * Manages the reactive list of GridCell objects, positions, and CRUD operations.
 *
 * Phase 2 — v2 architecture (no Pinia store injection, pure composable state).
 */

import { ref, readonly } from 'vue'
import type { GridCell, GridPosition, ViewSpec, CellTypeDefinition } from '../types'
import { createLogger } from '@/utils/logger'

const log = createLogger('workspace:grid-layout')

/** Simple UUID v4 generator (no external dependency) */
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// ── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_CELL_WIDTH = 6   // columns (out of 12)
const DEFAULT_CELL_HEIGHT = 8  // rows
const GRID_COLUMNS = 12

// ── Module-level reactive state (shared across composable calls) ─────────────

const cells = ref<GridCell[]>([])

// ── Composable ───────────────────────────────────────────────────────────────

export function useGridLayout() {

  // ── Helpers ───────────────────────────────────────────────────────────────

  /**
   * Calculate the next available grid position to place a new cell.
   * Simple packing: place right of the last cell, wrap when exceeding columns.
   */
  function getNextPosition(): GridPosition {
    if (cells.value.length === 0) {
      return { x: 0, y: 0, w: DEFAULT_CELL_WIDTH, h: DEFAULT_CELL_HEIGHT }
    }

    const last = cells.value[cells.value.length - 1].position
    const nextX = last.x + last.w

    if (nextX + DEFAULT_CELL_WIDTH > GRID_COLUMNS) {
      // Wrap to next row
      return {
        x: 0,
        y: last.y + last.h,
        w: DEFAULT_CELL_WIDTH,
        h: DEFAULT_CELL_HEIGHT,
      }
    }

    return { x: nextX, y: last.y, w: DEFAULT_CELL_WIDTH, h: DEFAULT_CELL_HEIGHT }
  }

  // ── Actions ───────────────────────────────────────────────────────────────

  /**
   * Add a new cell (in loading state) and return its UUID.
   * The caller is responsible for resolving viewSpec and updating the cell.
   *
   * @param cellTypeName  Semantic type name (e.g. "calculator-cell")
   * @param cellType      Full type definition (from HybridDatabase)
   * @returns             UUID of the new cell
   */
  function addCell(cellTypeName: string, cellType: CellTypeDefinition | null): string {
    const cellId = generateUUID()
    const position = getNextPosition()

    const newCell: GridCell = {
      cellId,
      cellTypeName,
      cellInstance: null,
      viewSpec: null,
      isLoading: true,
      error: null,
      isMinimized: false,
      isMaximized: false,
      position,
      cellType,
    }

    cells.value.push(newCell)
    log.info('[useGridLayout] Cell added', { cellId, cellTypeName })
    return cellId
  }

  /**
   * Remove a cell by ID.
   * @param cellId UUID of the cell to remove
   */
  function removeCell(cellId: string): void {
    const idx = cells.value.findIndex(c => c.cellId === cellId)
    if (idx !== -1) {
      cells.value.splice(idx, 1)
      log.info('[useGridLayout] Cell removed', { cellId })
    } else {
      log.warn('[useGridLayout] removeCell: cell not found', { cellId })
    }
  }

  /**
   * Partial update a cell (e.g. set viewSpec after it resolves).
   * @param cellId  UUID of the cell
   * @param updates Partial<GridCell> to merge
   */
  function updateCell(cellId: string, updates: Partial<GridCell>): void {
    const cell = cells.value.find(c => c.cellId === cellId)
    if (!cell) {
      log.warn('[useGridLayout] updateCell: cell not found', { cellId })
      return
    }
    Object.assign(cell, updates)
    log.debug('[useGridLayout] Cell updated', { cellId, updateKeys: Object.keys(updates) })
  }

  /**
   * Sync grid positions from an external layout update (e.g. drag/resize events).
   * @param updatedPositions Map of cellId → GridPosition
   */
  function syncLayoutPositions(updatedPositions: Record<string, GridPosition>): void {
    for (const cell of cells.value) {
      if (updatedPositions[cell.cellId]) {
        cell.position = updatedPositions[cell.cellId]
      }
    }
    log.debug('[useGridLayout] Layout positions synced', {
      count: Object.keys(updatedPositions).length,
    })
  }

  /**
   * Toggle minimized state for a cell.
   */
  function toggleMinimize(cellId: string): void {
    const cell = cells.value.find(c => c.cellId === cellId)
    if (cell) {
      cell.isMinimized = !cell.isMinimized
      if (cell.isMinimized) cell.isMaximized = false
      log.debug('[useGridLayout] Cell minimized toggle', { cellId, isMinimized: cell.isMinimized })
    }
  }

  /**
   * Toggle maximized state for a cell.
   */
  function toggleMaximize(cellId: string): void {
    const cell = cells.value.find(c => c.cellId === cellId)
    if (cell) {
      cell.isMaximized = !cell.isMaximized
      if (cell.isMaximized) cell.isMinimized = false
      log.debug('[useGridLayout] Cell maximized toggle', { cellId, isMaximized: cell.isMaximized })
    }
  }

  /**
   * Clear all cells (used when loading a new layout book).
   */
  function clearCells(): void {
    cells.value = []
    log.info('[useGridLayout] All cells cleared')
  }

  // ── Return ────────────────────────────────────────────────────────────────

  return {
    cells: readonly(cells),
    addCell,
    removeCell,
    updateCell,
    syncLayoutPositions,
    toggleMinimize,
    toggleMaximize,
    clearCells,
  }
}
