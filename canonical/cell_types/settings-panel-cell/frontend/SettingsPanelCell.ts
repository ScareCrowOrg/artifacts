/**
 * SettingsPanelCell - BaseCell implementation for settings management
 * 
 * Provides RBAC-aware settings management with conditional protection:
 * - User settings: No permission required
 * - Global settings: Requires settings:admin permission
 */

import { BaseCell } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError } from '@/types/BaseCell'
import { useAuthStore } from '@/stores/auth'

export class SettingsPanelCell extends BaseCell {
  /**
   * Execute settings operation with conditional RBAC
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const { action, scope, settings } = input
    
    // RBAC Check for global settings
    if (scope === 'global') {
      const hasAdminPermission = await this.checkPermission('settings:admin')
      if (!hasAdminPermission) {
        return {
          success: false,
          error: 'Permission denied: settings:admin required for global settings'
        }
      }
    }
    
    try {
      if (action === 'get') {
        const currentSettings = this.loadSettings(scope)
        return { 
          success: true, 
          action: 'get', 
          data: currentSettings 
        }
      }
      
      if (action === 'update') {
        if (!settings) {
          return { 
            success: false, 
            error: 'settings required for update action' 
          }
        }
        
        this.saveSettings(scope, settings)
        
        return { 
          success: true, 
          action: 'update', 
          data: settings 
        }
      }
      
      return { 
        success: false, 
        error: `Invalid action: ${action}` 
      }
    } catch (error: any) {
      return { 
        success: false, 
        error: error.message || 'Unknown error occurred' 
      }
    }
  }
  
  /**
   * Load settings from localStorage
   */
  private loadSettings(scope: 'user' | 'global'): any {
    const key = scope === 'user' 
      ? 'scareverse_user_settings' 
      : 'scareverse_global_settings'
    
    const stored = localStorage.getItem(key)
    return stored ? JSON.parse(stored) : {}
  }
  
  /**
   * Save settings to localStorage (and optionally backend)
   */
  private saveSettings(scope: 'user' | 'global', settings: any): void {
    const key = scope === 'user' 
      ? 'scareverse_user_settings' 
      : 'scareverse_global_settings'
    
    localStorage.setItem(key, JSON.stringify(settings))
    
    // TODO: Optional backend sync for global settings
    // if (scope === 'global') {
    //   await apiService.post('/api/settings/global', settings)
    // }
  }
  
  /**
   * Describe cell metadata
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'settings-panel-cell',
      name: 'Settings Panel',
      description: 'Manage user and global application settings with conditional RBAC',
      version: '1.0.0',
      author: 'ScareVerse',
      tags: ['settings', 'configuration', 'rbac', 'theme', 'oauth'],
      inputs: {
        action: { 
          type: 'enum', 
          required: true,
          description: 'Action to perform',
          enum_values: ['get', 'update']
        },
        scope: {
          type: 'enum',
          required: true,
          description: 'Scope of settings',
          enum_values: ['user', 'global']
        },
        settings: { 
          type: 'object', 
          required: false,
          description: 'Settings data for update action'
        }
      },
      outputs: {
        success: { 
          type: 'boolean',
          description: 'Operation success status'
        },
        action: { 
          type: 'string',
          description: 'Action that was performed'
        },
        data: { 
          type: 'object',
          description: 'Settings data'
        },
        error: {
          type: 'string',
          description: 'Error message if failed'
        }
      }
    }
  }
  
  /**
   * Validate input parameters
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    if (!input.action) {
      errors.push({ 
        field: 'action', 
        message: 'action is required' 
      })
    } else if (!['get', 'update'].includes(input.action)) {
      errors.push({ 
        field: 'action', 
        message: 'action must be "get" or "update"' 
      })
    }
    
    if (!input.scope) {
      errors.push({ 
        field: 'scope', 
        message: 'scope is required' 
      })
    } else if (!['user', 'global'].includes(input.scope)) {
      errors.push({ 
        field: 'scope', 
        message: 'scope must be "user" or "global"' 
      })
    }
    
    if (input.action === 'update' && !input.settings) {
      errors.push({ 
        field: 'settings', 
        message: 'settings is required for update action' 
      })
    }
    
    return errors
  }
  
  /**
   * Check if user has permission
   */
  private async checkPermission(permission: string): Promise<boolean> {
    try {
      const authStore = useAuthStore()
      return authStore.hasPermission(permission)
    } catch (error) {
      console.error('Error checking permission:', error)
      return false
    }
  }
}
