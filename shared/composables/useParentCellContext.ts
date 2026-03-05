/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-17",
 *   "console_calls_found": 6,
 *   "console_calls_migrated": 6,
 *   "migration_rate": 100,
 *   "logger_namespace": "cells:parent-context",
 *   "validation_status": "excellent"
 * }
 */
/**
 * @file useParentCellContext.ts
 * @description Composable for subviews to access parent cell context
 * 
 * This composable provides a standardized way for subview components to access
 * information about their parent cell without relying on prop drilling or
 * manual extraction logic.
 * 
 * Part of Epic #1108: Subview Architecture Refactoring
 */

import { inject, type InjectionKey, computed } from 'vue'
import type { ParentCellContext } from '@/types/RenderableCell'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:parent-context')

/**
 * Injection key for parent cell context
 * Used by parent cells to provide context to subviews
 */
export const PARENT_CELL_CONTEXT_KEY: InjectionKey<ParentCellContext> = Symbol('parentCellContext')

/**
 * Composable for subviews to access parent cell context
 * 
 * This composable should be used in subview components to get information about
 * the parent cell in a standardized way.
 * 
 * @param fallbackProps - Fallback props object (for backward compatibility)
 * @returns Parent cell context
 * 
 * @example
 * ```typescript
 * // In a subview component
 * const props = defineProps<{ cell: any }>()
 * const context = useParentCellContext(props.cell)
 * 
 * console.log('Parent cell ID:', context.cellId)
 * console.log('Parent cell type:', context.cellType)
 * ```
 */
export function useParentCellContext(fallbackProps?: any) {
  // Try to get context from Vue's provide/inject first
  const injectedContext = inject<ParentCellContext | null>(PARENT_CELL_CONTEXT_KEY, null)
  
  if (injectedContext) {
    log.debug('Using injected parent context')
    return {
      cellId: computed(() => injectedContext.cellId),
      cellType: computed(() => injectedContext.cellType),
      cellState: computed(() => injectedContext.cellState),
      cellApi: computed(() => injectedContext.cellApi),
    }
  }
  
  // Fallback to extracting from props (backward compatibility)
  log.warn('No injected context, falling back to props extraction')
  
  if (!fallbackProps) {
    log.warn('No fallback props provided and no injected context')
    return {
      cellId: computed(() => ''),
      cellType: computed(() => ''),
      cellState: computed(() => ({})),
      cellApi: computed(() => undefined),
    }
  }
  
  // Extract cellId using common patterns
  // Priority order:
  // 1. state.sourceCellId (when state is NOT spread to top level)
  // 2. sourceCellId (when state IS spread to top level - DynamicCellView case)
  // 3. id (fallback to current cell's own ID - not ideal for subviews)
  // 4. cellId (alternative property name)
  const cellId = computed(() => {
    return fallbackProps?.state?.sourceCellId || 
           fallbackProps?.sourceCellId ||
           fallbackProps?.id || 
           fallbackProps?.cellId || 
           ''
  })
  
  // Extract cellType using common patterns
  // Priority order:
  // 1. state.cellType (when state is NOT spread to top level)
  // 2. cellType directly on props (when state IS spread to top level - DynamicCellView case)
  // 3. type (alternative property name)
  const cellType = computed(() => {
    return fallbackProps?.state?.cellType || 
           fallbackProps?.cellType ||
           fallbackProps?.type || 
           ''
  })
  
  // Extract cell state
  const cellState = computed(() => {
    return fallbackProps?.state || {}
  })
  
  log.debug('Extracted from props', { cellId: cellId.value, cellType: cellType.value })
  
  return {
    cellId,
    cellType,
    cellState,
    cellApi: computed(() => undefined),
  }
}

/**
 * Type guard to check if context is valid
 */
export function hasValidParentContext(context: ReturnType<typeof useParentCellContext>): boolean {
  return !!context.cellId.value
}
