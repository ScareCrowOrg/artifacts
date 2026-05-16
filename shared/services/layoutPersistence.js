/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-14",
 *   "console_calls_found": 9,
 *   "console_calls_migrated": 9,
 *   "migration_rate": 100,
 *   "logger_namespace": "layout:persistence",
 *   "validation_status": "excellent"
 * }
 */
/**
 * @file layoutPersistence.js
 * @description Service for persisting and restoring layout state
 * 
 * Provides dual persistence strategy:
 * - localStorage: Fast local cache for immediate restore
 * - Backend API: Cross-device synchronization
 * 
 * Part of Phase 6: Layout Persistence & Restore (Issue #1034)
 */

import { ENDPOINTS } from '../config/endpoints.js'
import apiService from '@/services/apiService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('layout:persistence')

/**
 * Current layout data version
 * Increment when layout structure changes to handle migrations
 */
const LAYOUT_VERSION = '1.0.0'

/**
 * LocalStorage key for layout data
 */
const STORAGE_KEY = 'scareverse_dynamic_layout'

/**
 * Validation schema for layout data
 */
const LAYOUT_SCHEMA = {
  version: 'string',
  gridLayout: 'array',
  openCells: 'array',
  activeCellId: ['string', 'null'],
  footerVisible: 'boolean',
  timestamp: 'number'
}

/**
 * Validate layout data structure
 * 
 * Ensures the layout data conforms to the expected schema with required fields
 * and correct types. This prevents corrupted or malicious data from being saved.
 * 
 * Expected structure:
 * - version: string (e.g., "1.0.0")
 * - gridLayout: array of grid items with position/size info
 * - openCells: array of [cellId, metadata] tuples
 * - activeCellId: string or null (ID of focused cell)
 * - footerVisible: boolean
 * - timestamp: number (Unix timestamp in milliseconds)
 * 
 * @param {Object} data - Layout data to validate
 * @param {string} data.version - Schema version
 * @param {Array} data.gridLayout - Array of grid layout items
 * @param {Array} data.openCells - Array of open cell entries
 * @param {string|null} data.activeCellId - Currently active cell ID
 * @param {boolean} data.footerVisible - Footer visibility state
 * @param {number} data.timestamp - Save timestamp
 * @returns {Object} Validation result
 * @returns {boolean} result.isValid - Whether validation passed
 * @returns {string[]} result.errors - Array of error messages (empty if valid)
 */
function validateLayoutData(data) {
  const errors = []

  if (!data || typeof data !== 'object') {
    return { isValid: false, errors: ['Layout data must be an object'] }
  }

  // Check required fields
  for (const [key, expectedType] of Object.entries(LAYOUT_SCHEMA)) {
    if (!(key in data)) {
      errors.push(`Missing required field: ${key}`)
      continue
    }

    const value = data[key]
    const types = Array.isArray(expectedType) ? expectedType : [expectedType]
    const actualType = value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value

    if (!types.includes(actualType)) {
      errors.push(`Invalid type for ${key}: expected ${types.join(' or ')}, got ${actualType}`)
    }
  }

  // Validate gridLayout items
  if (Array.isArray(data.gridLayout)) {
    data.gridLayout.forEach((item, index) => {
      // Check for 'i' (required by vue3-grid-layout) and 'cellId'
      if (!item.i || !item.cellId) {
        errors.push(`Grid item ${index} missing required fields (i, cellId)`)
      }
      if (typeof item.x !== 'number' || typeof item.y !== 'number') {
        errors.push(`Grid item ${index} has invalid position`)
      }
      if (typeof item.w !== 'number' || typeof item.h !== 'number') {
        errors.push(`Grid item ${index} has invalid size`)
      }
    })
  }

  return {
    isValid: errors.length === 0,
    errors
  }
}

/**
 * Sanitize layout data before saving
 * @param {Object} data - Raw layout data
 * @returns {Object} Sanitized data
 */
function sanitizeLayoutData(data) {
  return {
    version: LAYOUT_VERSION,
    gridLayout: data.gridLayout || [],
    openCells: data.openCells || [],
    activeCellId: data.activeCellId || null,
    footerVisible: data.footerVisible !== undefined ? data.footerVisible : true,
    timestamp: Date.now()
  }
}

/**
 * Migrate layout data from older versions
 * @param {Object} data - Layout data to migrate
 * @returns {Object} Migrated data
 */
function migrateLayoutData(data) {
  // If no version, assume pre-versioning (version 0.0.0)
  const _currentVersion = data.version || '0.0.0'

  // No migrations needed yet (first version is 1.0.0)
  // Future migrations would go here:
  // if (_currentVersion < '1.1.0') { ... }

  return {
    ...data,
    version: LAYOUT_VERSION
  }
}

/**
 * Save layout to localStorage
 * @param {Object} layoutData - Layout data to save
 * @returns {Object} Result {success, error}
 */
export function saveToLocalStorage(layoutData) {
  try {
    const sanitized = sanitizeLayoutData(layoutData)
    const validation = validateLayoutData(sanitized)

    if (!validation.isValid) {
      log.error('Invalid layout data', validation.errors)
      return {
        success: false,
        error: `Validation failed: ${validation.errors.join(', ')}`
      }
    }

    const serialized = JSON.stringify(sanitized)
    localStorage.setItem(STORAGE_KEY, serialized)

    return { success: true }
  } catch (error) {
    log.error('Failed to save layout to localStorage', error)
    return {
      success: false,
      error: error.message
    }
  }
}

/**
 * Load layout from localStorage
 * @returns {Object} Result {success, data, error}
 */
export function loadFromLocalStorage() {
  try {
    const serialized = localStorage.getItem(STORAGE_KEY)
    if (!serialized) {
      return { success: false, error: 'No saved layout found' }
    }

    const data = JSON.parse(serialized)
    const migrated = migrateLayoutData(data)
    const validation = validateLayoutData(migrated)

    if (!validation.isValid) {
      log.error('Invalid layout data in localStorage', validation.errors)
      // Clear corrupted data
      localStorage.removeItem(STORAGE_KEY)
      return {
        success: false,
        error: `Invalid layout data: ${validation.errors.join(', ')}`
      }
    }

    return {
      success: true,
      data: migrated
    }
  } catch (error) {
    log.error('Failed to load layout from localStorage', error)
    // Clear corrupted data
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Ignore cleanup errors
    }
    return {
      success: false,
      error: error.message
    }
  }
}

/**
 * Clear layout from localStorage
 */
export function clearLocalStorage() {
  try {
    localStorage.removeItem(STORAGE_KEY)
    return { success: true }
  } catch (error) {
    log.error('Failed to clear localStorage', error)
    return {
      success: false,
      error: error.message
    }
  }
}

/**
 * Save layout to backend
 * @param {string} userId - User ID
 * @param {Object} layoutData - Layout data to save
 * @returns {Promise<Object>} Result {success, error}
 */
export async function saveToBackend(userId, layoutData) {
  try {
    const sanitized = sanitizeLayoutData(layoutData)
    const validation = validateLayoutData(sanitized)

    if (!validation.isValid) {
      return {
        success: false,
        error: `Validation failed: ${validation.errors.join(', ')}`
      }
    }

    const response = await apiService.fetch(ENDPOINTS.userLayout(userId), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ layout: sanitized })
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }

    const result = await response.json()

    return {
      success: true,
      data: result
    }
  } catch (error) {
    log.error('Failed to save layout to backend', error)
    return {
      success: false,
      error: error.message
    }
  }
}

/**
 * Load layout from backend
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Result {success, data, error}
 */
export async function loadFromBackend(userId) {
  try {
    const response = await apiService.fetch(ENDPOINTS.userLayout(userId), {
      method: 'GET'
    })

    if (response.status === 404) {
      // No layout saved yet
      return {
        success: false,
        error: 'No saved layout found'
      }
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }

    const result = await response.json()
    const layoutData = result.layout

    if (!layoutData) {
      return {
        success: false,
        error: 'Invalid response from backend'
      }
    }

    const migrated = migrateLayoutData(layoutData)
    const validation = validateLayoutData(migrated)

    if (!validation.isValid) {
      log.error('Invalid layout data from backend', validation.errors)
      return {
        success: false,
        error: `Invalid layout data: ${validation.errors.join(', ')}`
      }
    }

    return {
      success: true,
      data: migrated
    }
  } catch (error) {
    log.error('Failed to load layout from backend', error)
    return {
      success: false,
      error: error.message
    }
  }
}

/**
 * Sync layout between localStorage and backend
 * Uses "last write wins" strategy based on timestamp
 * @param {string} userId - User ID
 * @returns {Promise<Object>} Result {success, source, data, error}
 */
export async function syncLayout(userId) {
  try {
    // Load from both sources
    const localResult = loadFromLocalStorage()
    const backendResult = await loadFromBackend(userId)

    // If both failed, return error
    if (!localResult.success && !backendResult.success) {
      return {
        success: false,
        error: 'No layout found in localStorage or backend'
      }
    }

    // If only one succeeded, use that one
    if (localResult.success && !backendResult.success) {
      // Sync to backend for future
      await saveToBackend(userId, localResult.data)
      return {
        success: true,
        source: 'localStorage',
        data: localResult.data
      }
    }

    if (!localResult.success && backendResult.success) {
      // Sync to localStorage for future
      saveToLocalStorage(backendResult.data)
      return {
        success: true,
        source: 'backend',
        data: backendResult.data
      }
    }

    // Both succeeded - use most recent
    const localTimestamp = localResult.data.timestamp || 0
    const backendTimestamp = backendResult.data.timestamp || 0

    if (localTimestamp >= backendTimestamp) {
      // Local is newer, sync to backend
      await saveToBackend(userId, localResult.data)
      return {
        success: true,
        source: 'localStorage',
        data: localResult.data
      }
    } else {
      // Backend is newer, sync to local
      saveToLocalStorage(backendResult.data)
      return {
        success: true,
        source: 'backend',
        data: backendResult.data
      }
    }
  } catch (error) {
    log.error('Failed to sync layout', error)
    return {
      success: false,
      error: error.message
    }
  }
}

/**
 * Get default layout for first-time users
 * @returns {Object} Default layout data
 */
export function getDefaultLayout() {
  return {
    version: LAYOUT_VERSION,
    gridLayout: [],
    openCells: [],
    activeCellId: null,
    footerVisible: true,
    timestamp: Date.now()
  }
}

// Export LAYOUT_VERSION as named export for easy access
export { LAYOUT_VERSION }

export default {
  saveToLocalStorage,
  loadFromLocalStorage,
  clearLocalStorage,
  saveToBackend,
  loadFromBackend,
  syncLayout,
  getDefaultLayout,
  LAYOUT_VERSION
}
