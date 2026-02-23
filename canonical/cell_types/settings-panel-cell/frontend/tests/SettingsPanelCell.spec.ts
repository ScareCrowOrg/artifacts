/**
 * @file SettingsPanelCell.spec.ts
 * @description Unit tests for SettingsPanelCell
 * 
 * Tests the SettingsPanelCell BaseCell implementation with RBAC
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { SettingsPanelCell } from '../SettingsPanelCell'
import { setActivePinia, createPinia } from 'pinia'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} }
  }
})()

// Mock authStore
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    hasPermission: vi.fn((permission: string) => {
      return permission === 'settings:admin' ? mockHasAdminPermission : false
    })
  })
}))

let mockHasAdminPermission = false

describe('SettingsPanelCell', () => {
  let cell: SettingsPanelCell

  beforeEach(() => {
    setActivePinia(createPinia())
    cell = new SettingsPanelCell()
    
    // Setup localStorage mock
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true
    })
    
    localStorageMock.clear()
    mockHasAdminPermission = false
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('describe()', () => {
    it('should return correct metadata', async () => {
      const metadata = await cell.describe()

      expect(metadata.id).toBe('settings-panel-cell')
      expect(metadata.name).toBe('Settings Panel')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.tags).toContain('settings')
      expect(metadata.tags).toContain('rbac')
    })

    it('should define all input fields', async () => {
      const metadata = await cell.describe()

      expect(metadata.inputs.action).toBeDefined()
      expect(metadata.inputs.scope).toBeDefined()
      expect(metadata.inputs.settings).toBeDefined()
    })

    it('should define all output fields', async () => {
      const metadata = await cell.describe()

      expect(metadata.outputs.success).toBeDefined()
      expect(metadata.outputs.action).toBeDefined()
      expect(metadata.outputs.data).toBeDefined()
      expect(metadata.outputs.error).toBeDefined()
    })
  })

  describe('validate()', () => {
    it('should validate correct get input', () => {
      const input = {
        action: 'get',
        scope: 'user'
      }

      const errors = cell.validate(input)

      expect(errors).toHaveLength(0)
    })

    it('should validate correct update input', () => {
      const input = {
        action: 'update',
        scope: 'user',
        settings: { theme: 'dark' }
      }

      const errors = cell.validate(input)

      expect(errors).toHaveLength(0)
    })

    it('should reject missing action', () => {
      const input = {
        scope: 'user'
      }

      const errors = cell.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'action')).toBe(true)
    })

    it('should reject invalid action', () => {
      const input = {
        action: 'invalid',
        scope: 'user'
      }

      const errors = cell.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'action')).toBe(true)
    })

    it('should reject missing scope', () => {
      const input = {
        action: 'get'
      }

      const errors = cell.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'scope')).toBe(true)
    })

    it('should reject invalid scope', () => {
      const input = {
        action: 'get',
        scope: 'invalid'
      }

      const errors = cell.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'scope')).toBe(true)
    })

    it('should reject update without settings', () => {
      const input = {
        action: 'update',
        scope: 'user'
      }

      const errors = cell.validate(input)

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'settings')).toBe(true)
    })
  })

  describe('execute() - User Settings (No RBAC)', () => {
    it('should get user settings successfully', async () => {
      const input = {
        action: 'get',
        scope: 'user'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.action).toBe('get')
      expect(result.data).toBeDefined()
    })

    it('should update user settings successfully', async () => {
      const settings = { theme: 'dark', language: 'en' }
      const input = {
        action: 'update',
        scope: 'user',
        settings
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.action).toBe('update')
      expect(result.data).toEqual(settings)
      
      // Verify it was saved to localStorage
      const stored = localStorageMock.getItem('scareverse_user_settings')
      expect(stored).toBeDefined()
      expect(JSON.parse(stored!)).toEqual(settings)
    })

    it('should persist and retrieve user settings', async () => {
      // Save settings
      const settings = { theme: 'light', notifications: true }
      await cell.execute({
        action: 'update',
        scope: 'user',
        settings
      })

      // Retrieve settings
      const result = await cell.execute({
        action: 'get',
        scope: 'user'
      })

      expect(result.success).toBe(true)
      expect(result.data).toEqual(settings)
    })
  })

  describe('execute() - Global Settings (RBAC Protected)', () => {
    it('should deny global settings access without permission', async () => {
      mockHasAdminPermission = false
      
      const input = {
        action: 'get',
        scope: 'global'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toContain('Permission denied')
      expect(result.error).toContain('settings:admin')
    })

    it('should allow global settings access with permission', async () => {
      mockHasAdminPermission = true
      
      const input = {
        action: 'get',
        scope: 'global'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.action).toBe('get')
      expect(result.data).toBeDefined()
    })

    it('should update global settings with permission', async () => {
      mockHasAdminPermission = true
      
      const settings = { defaultTheme: 'light', oauthEnabled: true }
      const input = {
        action: 'update',
        scope: 'global',
        settings
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.action).toBe('update')
      expect(result.data).toEqual(settings)
      
      // Verify it was saved to localStorage
      const stored = localStorageMock.getItem('scareverse_global_settings')
      expect(stored).toBeDefined()
      expect(JSON.parse(stored!)).toEqual(settings)
    })

    it('should deny global settings update without permission', async () => {
      mockHasAdminPermission = false
      
      const input = {
        action: 'update',
        scope: 'global',
        settings: { defaultTheme: 'dark' }
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toContain('Permission denied')
    })
  })

  describe('execute() - Error Handling', () => {
    it('should return error for invalid action', async () => {
      const input = {
        action: 'delete',
        scope: 'user'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toContain('Invalid action')
    })

    it('should return error for update without settings', async () => {
      const input = {
        action: 'update',
        scope: 'user'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toContain('settings required')
    })
  })
})
