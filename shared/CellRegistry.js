/**
 * Cell Registry - Factory Pattern for Per-UUID Composable Instances
 * 
 * Manages the lifecycle of cell-specific composable instances to eliminate
 * singleton state patterns that cause race conditions and state pollution
 * in multi-instance cell environments.
 * 
 * Key Features:
 * - Factory-per-ID pattern: Each cell UUID gets isolated composable instances
 * - Lifecycle management: Automatic cleanup and memory leak prevention
 * - WeakMap support: Allows garbage collection when cells are destroyed
 * - Debug logging: Comprehensive logging for troubleshooting
 * 
 * Problem Solved:
 * - BEFORE: Multiple cells shared module-level reactive state (singleton)
 * - AFTER: Each cell gets its own isolated state instance
 * 
 * Usage Example:
 * ```javascript
 * import { getCellFactory } from '@/utils/CellRegistry'
 * 
 * // In component with cell UUID
 * const cellUuid = props.cellId
 * const factory = getCellFactory(cellUuid)
 * 
 * // Each cell gets isolated instance
 * factory.generateCellCode(cellUuid, content, 'auto')
 * ```
 * 
 * @module utils/CellRegistry
 * @version 1.0.0
 */

import { createLogger } from './logger'

const log = createLogger('registry:cells')

/**
 * Registry to store per-UUID composable instances
 * Map<string, Object> where key is cell UUID
 */
const cellRegistry = new Map()

/**
 * WeakMap for tracking cell component references
 * Allows garbage collection when components are destroyed
 */
const cellReferences = new WeakMap()

/**
 * Statistics for monitoring and debugging
 */
const registryStats = {
  totalCreated: 0,
  totalCleaned: 0,
  activeInstances: 0,
  creationTimestamps: new Map()
}

/**
 * Get or create a cell factory instance for a given UUID
 * 
 * This is the main entry point for the Factory-per-ID pattern.
 * Each unique cell UUID gets its own isolated composable instance.
 * 
 * @param {string} cellUuid - Unique cell identifier
 * @param {Function} factoryFunction - Factory function to create new instance
 * @returns {Object} Cell-specific composable instance
 * 
 * @example
 * const factory = getCellInstance(
 *   'cell-uuid-123',
 *   (uuid) => createCellFactoryInstance(uuid)
 * )
 */
export function getCellInstance(cellUuid, factoryFunction) {
  if (!cellUuid) {
    log.error('getCellInstance called without cellUuid', {
      stack: new Error().stack
    })
    throw new Error('cellUuid is required for getCellInstance')
  }

  // Check if instance already exists
  if (cellRegistry.has(cellUuid)) {
    log.debug('Returning existing cell instance', { cellUuid })
    return cellRegistry.get(cellUuid)
  }

  // Create new instance
  log.info('Creating new cell instance', { cellUuid })
  
  const instance = factoryFunction(cellUuid)
  
  // Store in registry
  cellRegistry.set(cellUuid, instance)
  
  // Update statistics
  registryStats.totalCreated++
  registryStats.activeInstances++
  registryStats.creationTimestamps.set(cellUuid, Date.now())
  
  log.debug('Cell instance created', {
    cellUuid,
    totalActive: registryStats.activeInstances,
    totalCreated: registryStats.totalCreated
  })
  
  return instance
}

/**
 * Check if a cell instance exists in the registry
 * 
 * @param {string} cellUuid - Cell UUID to check
 * @returns {boolean} True if instance exists
 */
export function hasCellInstance(cellUuid) {
  return cellRegistry.has(cellUuid)
}

/**
 * Get an existing cell instance without creating a new one
 * 
 * @param {string} cellUuid - Cell UUID
 * @returns {Object|null} Cell instance or null if not found
 */
export function getExistingCellInstance(cellUuid) {
  if (!cellUuid) {
    return null
  }
  return cellRegistry.get(cellUuid) || null
}

/**
 * Clean up a specific cell instance
 * 
 * Removes the instance from registry and calls cleanup if defined.
 * Should be called when a cell component is unmounted.
 * 
 * @param {string} cellUuid - Cell UUID to clean up
 * @returns {boolean} True if cleaned up, false if not found
 */
export function cleanupCellInstance(cellUuid) {
  if (!cellUuid) {
    log.warn('cleanupCellInstance called without cellUuid')
    return false
  }

  const instance = cellRegistry.get(cellUuid)
  
  if (!instance) {
    log.debug('No instance found to cleanup', { cellUuid })
    return false
  }

  log.info('Cleaning up cell instance', { cellUuid })
  
  // Call instance cleanup if defined
  if (typeof instance.cleanup === 'function') {
    try {
      instance.cleanup()
      log.debug('Instance cleanup() called successfully', { cellUuid })
    } catch (error) {
      log.error('Error during instance cleanup', { cellUuid, error: error.message })
    }
  }
  
  // Remove from registry
  cellRegistry.delete(cellUuid)
  registryStats.creationTimestamps.delete(cellUuid)
  
  // Update statistics
  registryStats.totalCleaned++
  registryStats.activeInstances--
  
  log.debug('Cell instance cleaned up', {
    cellUuid,
    totalActive: registryStats.activeInstances,
    totalCleaned: registryStats.totalCleaned
  })
  
  return true
}

/**
 * Clean up all cell instances
 * 
 * Useful for testing or complete reset scenarios.
 * Should rarely be needed in production.
 */
export function cleanupAllCellInstances() {
  log.info('Cleaning up all cell instances', {
    count: cellRegistry.size
  })
  
  const cellUuids = Array.from(cellRegistry.keys())
  
  for (const cellUuid of cellUuids) {
    cleanupCellInstance(cellUuid)
  }
  
  log.info('All cell instances cleaned up', {
    totalCleaned: registryStats.totalCleaned
  })
}

/**
 * Get registry statistics
 * 
 * Useful for monitoring, debugging, and memory leak detection.
 * 
 * @returns {Object} Registry statistics
 */
export function getRegistryStats() {
  return {
    ...registryStats,
    activeCellUuids: Array.from(cellRegistry.keys()),
    oldestInstance: getOldestInstanceInfo(),
    newestInstance: getNewestInstanceInfo()
  }
}

/**
 * Get info about the oldest active instance
 * @private
 */
function getOldestInstanceInfo() {
  if (registryStats.creationTimestamps.size === 0) {
    return null
  }
  
  let oldestUuid = null
  let oldestTimestamp = Infinity
  
  for (const [uuid, timestamp] of registryStats.creationTimestamps.entries()) {
    if (timestamp < oldestTimestamp) {
      oldestTimestamp = timestamp
      oldestUuid = uuid
    }
  }
  
  return oldestUuid ? {
    cellUuid: oldestUuid,
    ageMs: Date.now() - oldestTimestamp,
    createdAt: new Date(oldestTimestamp).toISOString()
  } : null
}

/**
 * Get info about the newest active instance
 * @private
 */
function getNewestInstanceInfo() {
  if (registryStats.creationTimestamps.size === 0) {
    return null
  }
  
  let newestUuid = null
  let newestTimestamp = 0
  
  for (const [uuid, timestamp] of registryStats.creationTimestamps.entries()) {
    if (timestamp > newestTimestamp) {
      newestTimestamp = timestamp
      newestUuid = uuid
    }
  }
  
  return newestUuid ? {
    cellUuid: newestUuid,
    ageMs: Date.now() - newestTimestamp,
    createdAt: new Date(newestTimestamp).toISOString()
  } : null
}

/**
 * Register a component reference for memory management
 * 
 * Uses WeakMap to allow garbage collection when component is destroyed.
 * 
 * @param {Object} componentInstance - Vue component instance
 * @param {string} cellUuid - Cell UUID
 */
export function registerComponentReference(componentInstance, cellUuid) {
  if (!componentInstance || !cellUuid) {
    log.warn('Invalid parameters for registerComponentReference', {
      hasComponent: !!componentInstance,
      hasCellUuid: !!cellUuid
    })
    return
  }
  
  cellReferences.set(componentInstance, cellUuid)
  
  log.debug('Component reference registered', { cellUuid })
}

/**
 * Check for potential memory leaks
 * 
 * Warns if instances have been alive for too long (default: 1 hour).
 * Should be called periodically in development.
 * 
 * @param {number} maxAgeMs - Maximum age in milliseconds (default: 1 hour)
 * @returns {Array<Object>} List of potentially leaked instances
 */
export function checkForMemoryLeaks(maxAgeMs = 60 * 60 * 1000) {
  const now = Date.now()
  const potentialLeaks = []
  
  for (const [uuid, timestamp] of registryStats.creationTimestamps.entries()) {
    const age = now - timestamp
    
    if (age > maxAgeMs) {
      potentialLeaks.push({
        cellUuid: uuid,
        ageMs: age,
        ageHours: (age / (60 * 60 * 1000)).toFixed(2),
        createdAt: new Date(timestamp).toISOString()
      })
    }
  }
  
  if (potentialLeaks.length > 0) {
    log.warn('Potential memory leaks detected', {
      count: potentialLeaks.length,
      instances: potentialLeaks
    })
  }
  
  return potentialLeaks
}

/**
 * Export registry for advanced use cases (testing, debugging)
 * 
 * ⚠️ WARNING: Direct registry manipulation can cause issues.
 * Use the provided API functions instead.
 */
export function _getRegistryForTesting() {
  if (import.meta.env.MODE !== 'test' && import.meta.env.DEV !== true) {
    log.error('_getRegistryForTesting should only be used in tests')
    throw new Error('_getRegistryForTesting is only available in test/dev mode')
  }
  
  return cellRegistry
}
