/**
 * System service - handles system-level operations like seeding data
 */

import { ENDPOINTS } from '@/config/endpoints.js'
import apiService from './apiService.js'

/**
 * Get system status
 * @returns {Promise<Object>} System status information
 */
export async function getSystemStatus() {
  const response = await apiService.fetch(ENDPOINTS.systemStatus)

  if (!response.ok) {
    throw new Error(`Failed to get system status: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Initialize seed data
 * Requires admin permissions
 * @returns {Promise<Object>} Seed data initialization result
 */
export async function initializeSeedData() {
  const response = await apiService.fetch(ENDPOINTS.systemSeedData, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(
      errorData.detail || `Failed to initialize seed data: ${response.statusText}`
    )
  }

  return response.json()
}

export default {
  getSystemStatus,
  initializeSeedData,
}
