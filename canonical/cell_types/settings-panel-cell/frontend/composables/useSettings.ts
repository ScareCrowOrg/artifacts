/**
 * useSettings - Composable for settings management logic
 * 
 * Provides reusable logic for interacting with settings
 */

import { ref, onMounted } from 'vue'
import type { SettingsPanelCell } from '../SettingsPanelCell'
import { useAuthStore } from '@/stores/auth'

export function useSettings(cellInstance: SettingsPanelCell) {
  const userSettings = ref<Record<string, any>>({})
  const globalSettings = ref<Record<string, any>>({})
  const hasAdminPermission = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)
  
  /**
   * Check if user has admin permission
   */
  async function checkAdminPermission(): Promise<boolean> {
    try {
      const authStore = useAuthStore()
      hasAdminPermission.value = await authStore.hasPermission('settings:admin')
      return hasAdminPermission.value
    } catch (err) {
      console.error('Error checking admin permission:', err)
      hasAdminPermission.value = false
      return false
    }
  }
  
  /**
   * Load user settings
   */
  async function loadUserSettings() {
    loading.value = true
    error.value = null
    
    try {
      const result = await cellInstance.execute({
        action: 'get',
        scope: 'user'
      })
      
      if (result.success) {
        userSettings.value = result.data || {}
      } else {
        error.value = result.error || 'Failed to load user settings'
      }
    } catch (err: any) {
      error.value = err.message || 'Unknown error'
    } finally {
      loading.value = false
    }
  }
  
  /**
   * Load global settings (requires admin permission)
   */
  async function loadGlobalSettings() {
    if (!hasAdminPermission.value) {
      return
    }
    
    loading.value = true
    error.value = null
    
    try {
      const result = await cellInstance.execute({
        action: 'get',
        scope: 'global'
      })
      
      if (result.success) {
        globalSettings.value = result.data || {}
      } else {
        error.value = result.error || 'Failed to load global settings'
      }
    } catch (err: any) {
      error.value = err.message || 'Unknown error'
    } finally {
      loading.value = false
    }
  }
  
  /**
   * Update user settings
   */
  async function updateUserSettings(newSettings: Record<string, any>) {
    loading.value = true
    error.value = null
    
    try {
      const result = await cellInstance.execute({
        action: 'update',
        scope: 'user',
        settings: newSettings
      })
      
      if (result.success) {
        userSettings.value = newSettings
        return true
      } else {
        error.value = result.error || 'Failed to update user settings'
        return false
      }
    } catch (err: any) {
      error.value = err.message || 'Unknown error'
      return false
    } finally {
      loading.value = false
    }
  }
  
  /**
   * Update global settings (requires admin permission)
   */
  async function updateGlobalSettings(newSettings: Record<string, any>) {
    if (!hasAdminPermission.value) {
      error.value = 'Permission denied: settings:admin required'
      return false
    }
    
    loading.value = true
    error.value = null
    
    try {
      const result = await cellInstance.execute({
        action: 'update',
        scope: 'global',
        settings: newSettings
      })
      
      if (result.success) {
        globalSettings.value = newSettings
        return true
      } else {
        error.value = result.error || 'Failed to update global settings'
        return false
      }
    } catch (err: any) {
      error.value = err.message || 'Unknown error'
      return false
    } finally {
      loading.value = false
    }
  }
  
  /**
   * Initialize settings on mount
   */
  async function initialize() {
    await checkAdminPermission()
    await loadUserSettings()
    
    if (hasAdminPermission.value) {
      await loadGlobalSettings()
    }
  }
  
  return {
    // State
    userSettings,
    globalSettings,
    hasAdminPermission,
    loading,
    error,
    
    // Methods
    checkAdminPermission,
    loadUserSettings,
    loadGlobalSettings,
    updateUserSettings,
    updateGlobalSettings,
    initialize,
  }
}
