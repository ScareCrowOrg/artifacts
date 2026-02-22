/**
 * Cell Instances Composable
 * 
 * Helper composable for cells to discover and communicate with other
 * running cell instances in the workspace.
 * 
 * Usage example:
 * ```typescript
 * import { useCellInstances } from '@artifacts/shared/composables/useCellInstances'
 * 
 * const { getChatInstance, sendToChat } = useCellInstances()
 * 
 * // Get chat-ia instance
 * const chatCell = getChatInstance()
 * if (chatCell) {
 *   chatCell.addAttachment('fragment.md', content, 'text')
 * }
 * 
 * // Or use helper
 * sendToChat('fragment.md', content)
 * ```
 * 
 * @module shared/composables/useCellInstances
 */

import { useCellInstancesStore } from '../stores/cellInstancesStore'
import type { CellInstanceMetadata } from '../stores/cellInstancesStore'

/**
 * Cell Instances Composable
 * 
 * Provides convenient methods for cell discovery and communication
 */
export function useCellInstances() {
  const cellInstancesStore = useCellInstancesStore()

  /**
   * Get the first chat-ia cell instance (if any)
   * 
   * @returns Chat cell metadata or null
   */
  function getChatInstance(): CellInstanceMetadata | null {
    return cellInstancesStore.getFirstInstanceByType('chat-ia')
  }

  /**
   * Send content to chat-ia cell (as attachment)
   * Convenience method for the common use case of sending fragments to chat
   * 
   * @param filename - Attachment filename
   * @param content - Attachment content
   * @param type - Content type (default: 'text')
   * @returns Success status
   */
  function sendToChat(filename: string, content: string, type = 'text'): boolean {
    const chatCell = getChatInstance()
    
    if (!chatCell || !chatCell.instance) {
      console.warn('[useCellInstances] Chat-IA cell not found or not registered')
      return false
    }

    // Try to call addAttachment method on the instance
    if (typeof chatCell.instance.addAttachment === 'function') {
      return chatCell.instance.addAttachment(filename, content, type)
    }

    console.warn('[useCellInstances] Chat instance does not have addAttachment method')
    return false
  }

  /**
   * Get a specific cell instance by ID
   * 
   * @param cellId - Cell identifier
   * @returns Cell metadata or null
   */
  function getCell(cellId: string): CellInstanceMetadata | null {
    return cellInstancesStore.getInstance(cellId)
  }

  /**
   * Get all instances of a specific cell type
   * 
   * @param cellType - Cell type identifier
   * @returns Array of matching cells
   */
  function getCellsByType(cellType: string): CellInstanceMetadata[] {
    return cellInstancesStore.getInstancesByType(cellType)
  }

  /**
   * Get all registered cell instances
   * 
   * @returns Array of all cells
   */
  function getAllCells(): CellInstanceMetadata[] {
    return cellInstancesStore.getAllInstances()
  }

  /**
   * Check if a specific cell type is available
   * 
   * @param cellType - Cell type identifier
   * @returns True if at least one instance exists
   */
  function hasCellType(cellType: string): boolean {
    return cellInstancesStore.getInstancesByType(cellType).length > 0
  }

  /**
   * Check if chat-ia is available
   * 
   * @returns True if chat-ia cell exists
   */
  function hasChatCell(): boolean {
    return hasCellType('chat-ia')
  }

  return {
    // Chat-specific helpers
    getChatInstance,
    sendToChat,
    hasChatCell,

    // Generic helpers
    getCell,
    getCellsByType,
    getAllCells,
    hasCellType,

    // Direct store access (for advanced use cases)
    store: cellInstancesStore
  }
}
