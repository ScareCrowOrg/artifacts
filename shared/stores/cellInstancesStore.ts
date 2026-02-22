/**
 * Cell Instances Store
 * 
 * Shared Pinia store that acts as a neutral bridge between cockpit-vue (core UI)
 * and cell-specific functionality in artifacts/. Allows cells to discover and
 * communicate with other running cell instances without tight coupling.
 * 
 * Architecture:
 * - cockpit-vue registers cell instances after creation
 * - Cells in artifacts/ query for instances by ID or type
 * - No cell-specific logic in cockpit-vue
 * 
 * @module shared/stores/cellInstancesStore
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Cell instance metadata stored in the registry
 */
export interface CellInstanceMetadata {
  /** Unique cell ID */
  cellId: string
  
  /** Cell type identifier */
  cellType: string
  
  /** Cell title/name */
  title?: string
  
  /** The actual cell instance (BaseCell or component instance) */
  instance: any
  
  /** Registration timestamp */
  registeredAt: Date
  
  /** Optional metadata */
  metadata?: Record<string, unknown>
}

/**
 * Cell Instances Store
 * 
 * Maintains a registry of all active cell instances in the workspace
 */
export const useCellInstancesStore = defineStore('cellInstances', () => {
  // State: Map of cellId -> CellInstanceMetadata
  const instances = ref<Map<string, CellInstanceMetadata>>(new Map())

  /**
   * Register a cell instance in the store
   * Called by DynamicWorkspace.vue after cell instantiation
   * 
   * @param cellId - Unique cell identifier
   * @param cellType - Cell type identifier
   * @param instance - The actual cell instance (BaseCell class or component)
   * @param metadata - Optional metadata (title, etc.)
   * @returns Success status
   */
  function registerInstance(
    cellId: string,
    cellType: string,
    instance: any,
    metadata?: { title?: string; [key: string]: unknown }
  ): boolean {
    if (!cellId || !cellType || !instance) {
      console.warn('[cellInstancesStore] Invalid registration parameters', {
        cellId,
        cellType,
        hasInstance: !!instance
      })
      return false
    }

    const instanceMetadata: CellInstanceMetadata = {
      cellId,
      cellType,
      title: metadata?.title,
      instance,
      registeredAt: new Date(),
      metadata
    }

    instances.value.set(cellId, instanceMetadata)
    
    console.debug('[cellInstancesStore] Cell instance registered', {
      cellId,
      cellType,
      title: metadata?.title,
      totalInstances: instances.value.size
    })

    return true
  }

  /**
   * Unregister a cell instance from the store
   * Called by DynamicWorkspace.vue when cell is removed/closed
   * 
   * @param cellId - Cell identifier to remove
   * @returns Success status
   */
  function unregisterInstance(cellId: string): boolean {
    if (!cellId) {
      console.warn('[cellInstancesStore] Invalid cellId for unregister')
      return false
    }

    const existed = instances.value.delete(cellId)
    
    if (existed) {
      console.debug('[cellInstancesStore] Cell instance unregistered', {
        cellId,
        remainingInstances: instances.value.size
      })
    }

    return existed
  }

  /**
   * Get a cell instance by ID
   * 
   * @param cellId - Cell identifier
   * @returns Cell instance metadata or null if not found
   */
  function getInstance(cellId: string): CellInstanceMetadata | null {
    if (!cellId) {
      return null
    }

    return instances.value.get(cellId) || null
  }

  /**
   * Get all cell instances of a specific type
   * 
   * @param cellType - Cell type identifier (e.g., 'chat-ia', 'file-editor')
   * @returns Array of matching cell instances
   */
  function getInstancesByType(cellType: string): CellInstanceMetadata[] {
    if (!cellType) {
      return []
    }

    return Array.from(instances.value.values()).filter(
      (meta) => meta.cellType === cellType
    )
  }

  /**
   * Get the first instance of a specific cell type
   * Useful when you expect only one instance of a cell type
   * 
   * @param cellType - Cell type identifier
   * @returns First matching instance or null
   */
  function getFirstInstanceByType(cellType: string): CellInstanceMetadata | null {
    const matches = getInstancesByType(cellType)
    return matches.length > 0 ? matches[0] : null
  }

  /**
   * Get all registered cell instances
   * 
   * @returns Array of all cell instance metadata
   */
  function getAllInstances(): CellInstanceMetadata[] {
    return Array.from(instances.value.values())
  }

  /**
   * Check if a cell instance is registered
   * 
   * @param cellId - Cell identifier
   * @returns True if instance exists
   */
  function hasInstance(cellId: string): boolean {
    return instances.value.has(cellId)
  }

  /**
   * Get count of registered instances
   * 
   * @returns Number of registered instances
   */
  function getInstanceCount(): number {
    return instances.value.size
  }

  /**
   * Clear all registered instances
   * Useful for testing or workspace reset
   */
  function clearAll(): void {
    instances.value.clear()
    console.debug('[cellInstancesStore] All instances cleared')
  }

  return {
    // State (readonly)
    instances,

    // Actions
    registerInstance,
    unregisterInstance,
    getInstance,
    getInstancesByType,
    getFirstInstanceByType,
    getAllInstances,
    hasInstance,
    getInstanceCount,
    clearAll
  }
})
