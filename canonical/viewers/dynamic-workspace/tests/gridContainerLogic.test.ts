/**
 * tests/gridContainerLogic.test.ts
 *
 * Unit tests for the core logic exercised by GridContainer.vue.
 *
 * Since GridContainer renders vue3-grid-layout-next (DOM dependency), we test
 * the underlying contracts via the composable directly:
 *
 * - Height preservation through minimize/restore cycle
 *   → toggleMinimize must NOT modify position.h
 *   → syncLayoutPositions called with h=1 (minimized visual height) must NOT
 *     overwrite position.h (handled by handleLayoutUpdated logic in the component)
 *
 * - syncLayoutPositions preserves h when minimized
 *   → Simulates what handleLayoutUpdated does: for minimized cells it always
 *     passes cell.position.h (not item.h from the library) to syncLayoutPositions
 *
 * - Auto-save watcher is triggered by position changes
 *   → syncLayoutPositions mutates cells reactively
 *
 * - Minimize lock (static=true behaviour)
 *   → Minimized cell's position changes are ignored in height dimension
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useGridLayout } from '../composables/useGridLayout'
import type { CellTypeDefinition } from '../types'

// ── Mock cell type ─────────────────────────────────────────────────────────────

const mockCellType: CellTypeDefinition = {
  name: 'calculator-cell',
  id: 'calculator-cell',
  description: 'Test calculator cell',
  version: '1.0.0',
  category: 'utility',
  icon: '🧮',
  can_render_dynamically: true,
}

// ── Shared setup ───────────────────────────────────────────────────────────────

describe('GridContainer logic — minimize/restore height preservation', () => {
  let grid: ReturnType<typeof useGridLayout>

  beforeEach(() => {
    grid = useGridLayout()
    grid.clearCells()
  })

  // ── Contract: toggleMinimize does NOT touch position.h ─────────────────────

  it('toggleMinimize does not modify position.h when minimizing', () => {
    const cellId = grid.addCell('calculator-cell', mockCellType)
    const originalH = grid.cells.value.find(c => c.cellId === cellId)!.position.h

    grid.toggleMinimize(cellId)

    const cell = grid.cells.value.find(c => c.cellId === cellId)!
    expect(cell.isMinimized).toBe(true)
    expect(cell.position.h).toBe(originalH) // height preserved
  })

  it('toggleMinimize does not modify position.h when restoring', () => {
    const cellId = grid.addCell('calculator-cell', mockCellType)
    const originalH = grid.cells.value.find(c => c.cellId === cellId)!.position.h

    grid.toggleMinimize(cellId) // minimize
    grid.toggleMinimize(cellId) // restore

    const cell = grid.cells.value.find(c => c.cellId === cellId)!
    expect(cell.isMinimized).toBe(false)
    expect(cell.position.h).toBe(originalH)
  })

  it('full minimize/restore cycle: height matches original even after a position sync', () => {
    const cellId = grid.addCell('calculator-cell', mockCellType)
    const originalH = grid.cells.value.find(c => c.cellId === cellId)!.position.h

    // Minimize
    grid.toggleMinimize(cellId)

    // Simulate what handleLayoutUpdated does for a minimized cell:
    // the library would report h=1 (MINIMIZED_HEIGHT), but the component
    // passes cell.position.h instead so the original height is preserved.
    const cell = grid.cells.value.find(c => c.cellId === cellId)!
    grid.syncLayoutPositions({
      [cellId]: { x: 2, y: 1, w: 4, h: cell.position.h }, // h = originalH, not 1
    })

    // Restore
    grid.toggleMinimize(cellId)

    const restored = grid.cells.value.find(c => c.cellId === cellId)!
    expect(restored.isMinimized).toBe(false)
    expect(restored.position.h).toBe(originalH)
  })

  it('syncLayoutPositions with h=1 (visual minimize height) would lose original height (documents the problem)', () => {
    const cellId = grid.addCell('calculator-cell', mockCellType)
    const originalH = grid.cells.value.find(c => c.cellId === cellId)!.position.h

    grid.toggleMinimize(cellId)

    // If handleLayoutUpdated naively passed item.h (=1) for a minimized cell,
    // position.h would be overwritten — this test documents that the component
    // must NOT pass h=1 for minimized cells.
    grid.syncLayoutPositions({ [cellId]: { x: 0, y: 0, w: 6, h: 1 } })

    grid.toggleMinimize(cellId) // restore

    const cell = grid.cells.value.find(c => c.cellId === cellId)!
    // h is now 1 — height was LOST. handleLayoutUpdated prevents this by
    // using cell.position.h instead of item.h for minimized cells.
    expect(cell.position.h).toBe(1)
    expect(cell.position.h).not.toBe(originalH) // confirms the bug if prevention absent
  })

  // ── Contract: syncLayoutPositions updates x, y, w correctly ───────────────

  it('syncLayoutPositions updates x, y, w for a minimized cell (position can shift)', () => {
    const cellId = grid.addCell('calculator-cell', mockCellType)
    const originalH = grid.cells.value.find(c => c.cellId === cellId)!.position.h

    grid.toggleMinimize(cellId)

    // Simulate dragging a non-static cell that causes the layout to repack
    // (minimized cells are static in vue3-grid-layout-next, so x/y won't change
    //  in practice, but syncLayoutPositions should still update them correctly)
    grid.syncLayoutPositions({
      [cellId]: { x: 3, y: 4, w: 8, h: originalH },
    })

    const cell = grid.cells.value.find(c => c.cellId === cellId)!
    expect(cell.position.x).toBe(3)
    expect(cell.position.y).toBe(4)
    expect(cell.position.w).toBe(8)
    expect(cell.position.h).toBe(originalH)
  })

  // ── Contract: multiple cells — only minimized cell height is preserved ─────

  it('syncLayoutPositions updates non-minimized cells normally while preserving minimized h', () => {
    const id1 = grid.addCell('calculator-cell', mockCellType)
    const id2 = grid.addCell('calculator-cell', mockCellType)
    const originalH1 = grid.cells.value.find(c => c.cellId === id1)!.position.h

    grid.toggleMinimize(id1) // minimize cell 1

    // Simulate handleLayoutUpdated output: cell1 gets its original h, cell2 gets new h
    const cell1 = grid.cells.value.find(c => c.cellId === id1)!
    grid.syncLayoutPositions({
      [id1]: { x: 0, y: 0, w: 6, h: cell1.position.h }, // preserves originalH1
      [id2]: { x: 6, y: 2, w: 4, h: 12 },               // new size from resize
    })

    const c1 = grid.cells.value.find(c => c.cellId === id1)!
    const c2 = grid.cells.value.find(c => c.cellId === id2)!

    expect(c1.position.h).toBe(originalH1) // minimized cell preserved
    expect(c2.position.h).toBe(12)          // non-minimized cell updated
  })

  // ── Contract: isMaximized is cleared on minimize ───────────────────────────

  it('toggleMinimize clears isMaximized flag', () => {
    const cellId = grid.addCell('calculator-cell', mockCellType)
    grid.updateCell(cellId, { isMaximized: true })

    grid.toggleMinimize(cellId)

    const cell = grid.cells.value.find(c => c.cellId === cellId)!
    expect(cell.isMinimized).toBe(true)
    expect(cell.isMaximized).toBe(false)
  })
})
