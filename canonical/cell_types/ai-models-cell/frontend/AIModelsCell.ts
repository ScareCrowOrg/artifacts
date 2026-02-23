/**
 * @file AIModelsCell.ts
 * @description AI Models Cell - BaseCell implementation for AI model configuration management
 * 
 * Provides secure, permission-protected interface for managing AI model configurations
 * across multiple providers (Ollama, Gemini, OpenAI).
 * Requires 'ai-models:admin' permission for all operations.
 * 
 * Part of BaseCell v1.0 Framework - Admin cells category
 */

import { BaseCell } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  HealthCheckResult
} from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:AIModels')

/**
 * AI Models actions
 */
export type AIModelsAction = 'get' | 'update' | 'test-connection'

/**
 * AI Model provider types
 */
export type AIModelProvider = 'ollama' | 'gemini' | 'openai'

/**
 * Provider configuration structure
 */
export interface ProviderConfig {
  endpoint?: string
  apiKey?: string
  modelName?: string
  [key: string]: any
}

/**
 * Input for AI Models cell
 */
export interface AIModelsInput {
  action: AIModelsAction
  provider?: AIModelProvider
  config?: ProviderConfig
}

/**
 * AI Models Cell
 * 
 * RBAC-protected cell for managing AI model configurations.
 * All operations require 'ai-models:admin' permission.
 */
export class AIModelsCell extends BaseCell {
  /**
   * Check if user has required permission
   * @private
   */
  private async checkPermission(permission: string): Promise<boolean> {
    const authStore = useAuthStore()
    
    if (!authStore.isAuthenticated || !authStore.currentUser) {
      log.warn('Permission check failed: User not authenticated')
      return false
    }
    
    try {
      const { usePermissions } = await import('@/composables/usePermissions')
      const permissions = usePermissions()
      const hasPermission = await permissions.can(permission)
      
      log.debug('Permission check', {
        permission,
        hasPermission,
        user: authStore.currentUser.email
      })
      
      return hasPermission
    } catch (error) {
      log.error('Permission check error', error)
      return false
    }
  }

  /**
   * Get current configuration for a provider
   * @private
   */
  private async getModelConfig(provider?: AIModelProvider): Promise<any> {
    try {
      if (provider) {
        const response = await apiFetch(`/api/ai-models/config/${provider}`)
        if (!response.ok) {
          throw new Error(`Failed to get config for ${provider}`)
        }
        return await response.json()
      } else {
        // Get all configurations
        const response = await apiFetch('/api/ai-models/config')
        if (!response.ok) {
          throw new Error('Failed to get configurations')
        }
        return await response.json()
      }
    } catch (error: any) {
      log.error('Error getting model config', { provider, error })
      throw error
    }
  }

  /**
   * Save configuration for a provider
   * @private
   */
  private async saveModelConfig(provider: AIModelProvider, config: ProviderConfig): Promise<any> {
    try {
      const response = await apiFetch(`/api/ai-models/config/${provider}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })
      
      if (!response.ok) {
        throw new Error(`Failed to save config for ${provider}`)
      }
      
      return await response.json()
    } catch (error: any) {
      log.error('Error saving model config', { provider, error })
      throw error
    }
  }

  /**
   * Test connection to a provider
   * @private
   */
  private async testConnection(provider: AIModelProvider, config: ProviderConfig): Promise<boolean> {
    try {
      const response = await apiFetch(`/api/ai-models/test-connection/${provider}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })
      
      if (!response.ok) {
        log.warn('Connection test failed', { provider })
        return false
      }
      
      const result = await response.json()
      return result.connected === true
    } catch (error: any) {
      log.error('Error testing connection', { provider, error })
      return false
    }
  }

  /**
   * Execute AI models configuration action
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = Date.now()
    
    // MANDATORY: Check permission FIRST
    const hasPermission = await this.checkPermission('ai-models:admin')
    if (!hasPermission) {
      return {
        success: false,
        output: {
          message: 'Permission denied: ai-models:admin required'
        },
        error: 'Permission denied: ai-models:admin required',
        execution_time: Date.now() - startTime
      }
    }
    
    // Validate input
    const errors = this.validate(input)
    if (errors.length > 0) {
      return {
        success: false,
        output: {
          errors
        },
        error: 'Validation failed',
        execution_time: Date.now() - startTime
      }
    }
    
    const { action, provider, config } = input as AIModelsInput
    
    try {
      let result: any
      
      switch (action) {
        case 'get':
          result = await this.getModelConfig(provider)
          return {
            success: true,
            output: {
              action: 'get',
              provider,
              config: result
            },
            execution_time: Date.now() - startTime
          }
          
        case 'update':
          if (!provider) {
            throw new Error('provider required for update action')
          }
          if (!config) {
            throw new Error('config required for update action')
          }
          result = await this.saveModelConfig(provider, config)
          return {
            success: true,
            output: {
              action: 'update',
              provider,
              config: result
            },
            execution_time: Date.now() - startTime
          }
          
        case 'test-connection':
          if (!provider) {
            throw new Error('provider required for test-connection action')
          }
          if (!config) {
            throw new Error('config required for test-connection action')
          }
          const connected = await this.testConnection(provider, config)
          return {
            success: connected,
            output: {
              action: 'test-connection',
              provider,
              connected
            },
            execution_time: Date.now() - startTime
          }
          
        default:
          throw new Error(`Invalid action: ${action}`)
      }
    } catch (error: any) {
      log.error('Execute error', { action, provider, error })
      return {
        success: false,
        output: {},
        error: error.message || 'AI Models operation failed',
        execution_time: Date.now() - startTime
      }
    }
  }

  /**
   * Describe cell capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'ai-models-cell',
      name: 'AI Models Configuration',
      version: '1.0.0',
      description: 'Manage AI model configurations (RBAC protected)',
      inputs: {
        action: {
          type: 'enum',
          required: true,
          values: ['get', 'update', 'test-connection'],
          description: 'Action to perform'
        },
        provider: {
          type: 'string',
          required: false,
          enum: ['ollama', 'gemini', 'openai'],
          description: 'AI model provider'
        },
        config: {
          type: 'object',
          required: false,
          description: 'Provider-specific configuration'
        }
      },
      outputs: {
        success: { type: 'boolean', description: 'Operation success status' },
        action: { type: 'string', description: 'Action performed' },
        provider: { type: 'string', description: 'Provider targeted' },
        config: { type: 'object', description: 'Configuration data' },
        connected: { type: 'boolean', description: 'Connection test result' }
      },
      tags: ['admin', 'ai', 'models', 'configuration', 'rbac'],
      estimated_duration_seconds: 2,
      required_resources: ['internet']
    }
  }

  /**
   * Validate input
   */
  validate(input: any): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.action) {
      errors.push({ field: 'action', message: 'Action is required' })
    }

    if (input.action && !['get', 'update', 'test-connection'].includes(input.action)) {
      errors.push({ field: 'action', message: 'Invalid action. Must be get, update, or test-connection' })
    }

    if (input.action === 'update' || input.action === 'test-connection') {
      if (!input.provider) {
        errors.push({ field: 'provider', message: 'Provider is required for this action' })
      }
      
      if (!input.config) {
        errors.push({ field: 'config', message: 'Config is required for this action' })
      }
    }

    if (input.provider && !['ollama', 'gemini', 'openai'].includes(input.provider)) {
      errors.push({ field: 'provider', message: 'Invalid provider. Must be ollama, gemini, or openai' })
    }

    return errors
  }

  /**
   * Health check
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      // Check if backend AI models API is accessible
      const response = await apiFetch('/api/ai-models/health')
      
      if (response.ok) {
        return {
          status: 'healthy',
          can_execute: true
        }
      } else {
        return {
          status: 'degraded',
          can_execute: true,
          reason: 'AI models API partially unavailable'
        }
      }
    } catch (error) {
      return {
        status: 'degraded',
        can_execute: true,
        reason: 'Cannot connect to AI models API (will retry on execute)'
      }
    }
  }
}

/**
 * Export default for dynamic imports
 */
export default AIModelsCell
