/**
 * @file useBaseCellFeatures.ts
 * @description Composable that implements RenderableCell interface
 * 
 * This composable provides a complete implementation of RenderableCell,
 * combining execution capabilities from BaseCell with UI rendering,
 * persistence, and fragment management.
 * 
 * Part of BaseCell v1.0 Framework Implementation
 * Epic: Phase 1 - Foundation
 * Task: [BC-TS-003] Create useBaseCellFeatures composable
 */

import { ref, computed, type Ref } from 'vue'
import type { RenderableCell, ShowOptions, SubViewConfig, ParentCellContext } from '@/types/RenderableCell'
import type { CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult, CellFragment } from '@/types/BaseCell'
import type { CompleteCell } from '@/types/cell'
import { useNotebookStore } from '@/stores/useNotebookStore'
import { useCellsStore } from '@/stores/cells'
import { useChatStore } from '@/stores/chat'
import { useLayoutStore } from '@/stores/layout'
import apiService from '@/services/apiService.js'
import { ENDPOINTS } from '@/config/endpoints.js'

/**
 * Options for useBaseCellFeatures
 */
export interface UseBaseCellFeaturesOptions {
  /** Enable auto-save functionality */
  autoSave?: boolean
  
  /** Auto-save delay in milliseconds */
  autoSaveDelay?: number
  
  /** Enable fragment management */
  enableFragments?: boolean
  
  /** Custom save handler (overrides default) */
  customSaveHandler?: () => Promise<void>
}

/**
 * Build complete cell payload for API persistence
 * Ensures all cell fields are included in the save operation
 */
function buildCellPayload(cell: CompleteCell): Record<string, unknown> {
  return {
    initial_data: cell.initial_data || cell.data || {},
    fragments: cell.fragments || [],
    metadata: cell.metadata || {},
    status: cell.status,
    history: cell.history || [],
    title: cell.title,
    content: cell.content,
  }
}

/**
 * Use base cell features composable
 * 
 * Returns a RenderableCell implementation with all required methods.
 * This should be the foundation for all cell-specific composables.
 * 
 * @param cellId - Reactive cell ID
 * @param cellType - Reactive cell type
 * @param cellInstance - Reactive cell instance (REQUIRED for proper instance injection)
 * @param baseCell - BaseCell implementation (provides execute, describe, validate)
 * @param options - Configuration options
 * @returns RenderableCell implementation
 * 
 * @example
 * ```typescript
 * // In a cell component
 * const calculatorCell = new CalculatorCell()
 * const renderable = useBaseCellFeatures(
 *   computed(() => props.cell.id),
 *   computed(() => 'calculator-cell'),
 *   ref(props.cell),
 *   calculatorCell,
 *   { enableFragments: true }
 * )
 * 
 * // Execute headless
 * const result = await renderable.execute({ a: 5, b: 3, operation: 'add' })
 * 
 * // Show in workspace
 * await renderable.show({ a: 5, b: 3 }, { mode: 'workspace' })
 * 
 * // Save to backend
 * await renderable.saveCell(props.cell)
 * ```
 */
export function useBaseCellFeatures(
  cellId: Ref<string>,
  cellType: Ref<string>,
  cellInstance: Ref<CompleteCell>,
  baseCell: { 
    execute: (input: Record<string, any>) => Promise<CellResult>
    describe: () => Promise<CellMetadata>
    validate: (input: Record<string, any>) => ValidationError[]
    setup?: (config: EnvironmentConfig) => Promise<void>
    teardown?: () => Promise<void>
    health_check?: () => Promise<HealthCheckResult>
  },
  options: UseBaseCellFeaturesOptions = {}
): RenderableCell {
  // ============================================================
  // Stores
  // ============================================================
  const notebookStore = useNotebookStore()
  const cellsStore = useCellsStore()
  const chatStore = useChatStore()
  const layoutStore = useLayoutStore()

  // ============================================================
  // State
  // ============================================================
  const isLoading = ref(false)
  const isSaving = ref(false)
  const errorMessage = ref<string | null>(null)
  const successMessage = ref<string | null>(null)
  
  // Subviews registry
  const subViews = ref<Map<string, SubViewConfig>>(new Map())
  const renderedSubViews = ref<Map<string, string>>(new Map())

  // Auto-clear timers
  let successTimer: ReturnType<typeof setTimeout> | null = null
  let errorTimer: ReturnType<typeof setTimeout> | null = null

  // ============================================================
  // Message Methods
  // ============================================================
  
  function showSuccess(message: string, duration: number = 3000): void {
    errorMessage.value = null
    successMessage.value = message
    
    if (successTimer) clearTimeout(successTimer)
    successTimer = setTimeout(() => {
      successMessage.value = null
    }, duration)
  }

  function showError(message: string): void {
    successMessage.value = null
    errorMessage.value = message
    
    if (errorTimer) clearTimeout(errorTimer)
    errorTimer = setTimeout(() => {
      errorMessage.value = null
    }, 5000)
  }

  function clearMessages(): void {
    if (successTimer) clearTimeout(successTimer)
    if (errorTimer) clearTimeout(errorTimer)
    successMessage.value = null
    errorMessage.value = null
  }

  // ============================================================
  // BaseCell Methods (delegated)
  // ============================================================
  
  async function execute(input: Record<string, any>): Promise<CellResult> {
    return await baseCell.execute(input)
  }

  async function describe(): Promise<CellMetadata> {
    return await baseCell.describe()
  }

  function validate(input: Record<string, any>): ValidationError[] {
    return baseCell.validate(input)
  }

  async function setup(config: EnvironmentConfig): Promise<void> {
    if (baseCell.setup) {
      await baseCell.setup(config)
    }
  }

  async function teardown(): Promise<void> {
    if (baseCell.teardown) {
      await baseCell.teardown()
    }
  }

  async function health_check(): Promise<HealthCheckResult> {
    if (baseCell.health_check) {
      return await baseCell.health_check()
    }
    return {
      status: 'healthy',
      can_execute: true
    }
  }

  // ============================================================
  // RenderableCell Methods
  // ============================================================
  
  async function show(setupData: Record<string, any>, options: ShowOptions): Promise<void> {
    if (options.mode === 'headless') {
      // Headless mode: just execute without UI
      await execute(setupData)
      return
    }

    if (options.mode === 'workspace') {
      // Workspace mode: add to dynamic grid
      layoutStore.addCell({
        cellId: cellId.value,
        type: cellType.value,
        title: cellType.value, // Use cell type as title
        state: setupData,
        position: options.position || {
          x: 0,
          y: 0,
          w: 6,
          h: 4
        }
      })
      return
    }

    if (options.mode === 'modal') {
      // Modal mode: show as overlay isolated from grid
      // Register a modal for this cell if not already registered
      const modalId = `cell-modal-${cellId.value}`
      const modalsStore = await import('@/stores/modals').then(m => m.useModalsStore())
      
      // Register the cell modal
      // Note: 'component' is metadata for the modal system
      // Actual rendering is handled by CellModal.vue which monitors modal state
      modalsStore.registerModal(modalId, {
        component: 'CellModal',  // Identifier for debugging/logging
        persistent: false,
        zIndex: 1000
      })
      
      // Open the modal with cell configuration
      modalsStore.openModal(modalId, {
        props: {
          cellId: cellId.value,
          cellType: cellType.value,
          title: options.title || cellType.value,
          initialData: setupData
        },
        onClose: () => {
          modalsStore.unregisterModal(modalId)
        }
      })
      
      return
    }
  }

  async function saveCell(cellInstanceParam?: CompleteCell): Promise<void> {
    if (!cellId.value) {
      showError('Cannot save cell without ID')
      return
    }

    isSaving.value = true
    errorMessage.value = null
    successMessage.value = null

    try {
      // Use custom save handler if provided
      if (options.customSaveHandler) {
        await options.customSaveHandler()
      } else {
        // Use provided cell instance parameter, or fall back to composable's cell instance
        const cell = cellInstanceParam || cellInstance.value
        
        if (!cell) {
          throw new Error('Cell instance not found')
        }

        // Build complete cell payload
        const payload = buildCellPayload(cell)

        // Save to backend via API
        const response = await apiService.fetch(
          ENDPOINTS.updateCell(cellId.value),
          {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          }
        ) as Response

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(`Failed to save cell: ${response.statusText}`)
        }

        const updatedCell: any = await response.json()
        
        // Update the cell in the store
        const cells = notebookStore.cells as Record<string, any>
        cells[cellId.value] = updatedCell
      }

      showSuccess('Cell saved successfully!')
    } catch (error: any) {
      showError(error.message || 'Error saving cell')
      throw error
    } finally {
      isSaving.value = false
    }
  }

  async function addFragment(cell: CompleteCell, fragmentData: CellFragment): Promise<void> {
    if (!cell.fragments) {
      cell.fragments = []
    }
    
    cell.fragments.push(fragmentData)
    
    // Auto-save if enabled
    if (options.autoSave) {
      await saveCell(cell)
    }
  }

  function sendFragmentToChat(fragment: CellFragment, index: number): void {
    const filename = `Fragment #${index + 1} - ${fragment.type || 'unknown'}`
    const content = fragment.conteudo || fragment.content || ''
    chatStore.addAttachment(filename, content, 'text')
  }

  function showCellFragmentsManager(): void {
    if (!cellId.value) {
      showError('Cannot show fragments manager without cell ID')
      return
    }

    // Render the fragments manager subview
    renderSubView('fragments-manager', {
      cellId: cellId.value,
      cellType: cellType.value,
      cellInstance: cellInstance.value
    })
  }

  function registerSubView(config: SubViewConfig): void {
    subViews.value.set(config.id, config)
  }

  function renderSubView(subViewId: string, props?: Record<string, any>): string | null {
    const config = subViews.value.get(subViewId)
    
    if (!config) {
      console.warn(`Subview '${subViewId}' not registered`)
      return null
    }

    // Generate unique instance ID
    const instanceId = `${subViewId}-${Date.now()}`
    
    // Add to layout based on render mode
    if (config.renderMode === 'grid') {
      layoutStore.addCell({
        cellId: instanceId,
        type: typeof config.component === 'string' ? config.component : 'custom-subview',
        title: config.label || 'Subview',
        state: {
          ...config.defaultProps,
          ...props,
          parentCellId: cellId.value,
          parentCellType: cellType.value
        },
        position: config.gridPosition || {
          x: 0,
          y: 0,
          w: 6,
          h: 4
        }
      })
    }
    
    // Track rendered subview
    renderedSubViews.value.set(instanceId, subViewId)
    
    return instanceId
  }

  function closeSubView(instanceId: string): void {
    layoutStore.removeCell(instanceId)
    renderedSubViews.value.delete(instanceId)
  }

  function getParentContext(): ParentCellContext {
    return {
      cellId: cellId.value,
      cellType: cellType.value,
      cellState: cellInstance.value.initial_data,
      cellApi: renderableCell as RenderableCell
    }
  }

  function closeCell(): void {
    if (!cellId.value) {
      return
    }

    cellsStore.closeCellView(cellId.value)
    layoutStore.removeCell(cellId.value)
  }

  // ============================================================
  // Initialization
  // ============================================================
  
  // Auto-register fragments manager subview
  const fragmentsManagerConfig: SubViewConfig = {
    id: 'fragments-manager',
    label: '📚 Fragments Manager',
    component: 'base_cell_components/frontend/views/BaseFragmentsManager.vue',
    renderMode: 'grid',
    gridPosition: {
      w: 6,
      h: 8,
    },
  }
  
  registerSubView(fragmentsManagerConfig)

  // ============================================================
  // Return RenderableCell Interface
  // ============================================================
  
  const renderableCell: RenderableCell = {
    // BaseCell methods
    execute,
    describe,
    validate,
    setup,
    teardown,
    health_check,
    run: async (lifecycle: any) => {
      // Stub - not implemented in composable
      throw new Error('run() not implemented in useBaseCellFeatures')
    },
    
    // RenderableCell methods
    show,
    saveCell,
    addFragment,
    sendFragmentToChat,
    showCellFragmentsManager,
    registerSubView,
    renderSubView,
    closeSubView,
    getParentContext,
    closeCell,
    showSuccess,
    showError,
    clearMessages
  } as unknown as RenderableCell

  return renderableCell
}
