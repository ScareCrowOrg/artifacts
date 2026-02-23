/**
 * @file AdminSettings.spec.ts
 * @description Component tests for AdminSettings with RBAC
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import AdminSettings from '../../components/AdminSettings.vue'
import { useSettingsPanelStore } from '../../stores/settingsStore'

// Mock i18n
const mockI18n = {
  t: (key: string) => key
}

// Mock apiService
vi.mock('@/services/apiService', () => ({
  default: {
    fetch: vi.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        authEnabled: false,
        configured: false,
        client_id: ''
      })
    }))
  }
}))

// Mock ENDPOINTS
vi.mock('@/config/endpoints', () => ({
  ENDPOINTS: {
    authGoogleStatus: '/api/auth/google/status',
    authGoogleConfig: '/api/auth/google/config'
  }
}))

describe('AdminSettings Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should render admin settings section', () => {
    const wrapper = mount(AdminSettings, {
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    expect(wrapper.find('.admin-settings').exists()).toBe(true)
    expect(wrapper.text()).toContain('Admin Settings')
  })

  it('should display OAuth configuration form', () => {
    const wrapper = mount(AdminSettings, {
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    expect(wrapper.find('#clientId').exists()).toBe(true)
    expect(wrapper.find('#clientSecret').exists()).toBe(true)
  })

  it('should have save button', () => {
    const wrapper = mount(AdminSettings, {
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    const saveButton = wrapper.find('button.btn-primary')
    expect(saveButton.exists()).toBe(true)
  })

  it('should disable save button when no changes', async () => {
    const wrapper = mount(AdminSettings, {
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    await wrapper.vm.$nextTick()

    const saveButton = wrapper.find('button.btn-primary')
    expect(saveButton.attributes('disabled')).toBeDefined()
  })

  it('should call saveOAuthConfig on save button click', async () => {
    const wrapper = mount(AdminSettings, {
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    const store = useSettingsPanelStore()
    const saveSpy = vi.spyOn(store, 'saveOAuthConfig')

    // Enable save button by changing config
    store.oauthConfig.googleClientId = 'test-id'
    await wrapper.vm.$nextTick()

    const saveButton = wrapper.find('button.btn-primary')
    await saveButton.trigger('click')

    expect(saveSpy).toHaveBeenCalled()
  })

  it('should display auth status badge', () => {
    const wrapper = mount(AdminSettings, {
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    const statusBadge = wrapper.find('span.px-2')
    expect(statusBadge.exists()).toBe(true)
  })

  it('should load OAuth status on mount', async () => {
    const store = useSettingsPanelStore()
    const loadSpy = vi.spyOn(store, 'loadOAuthStatus')

    const wrapper = mount(AdminSettings, {
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    // Wait for onMounted hook
    await new Promise(resolve => setTimeout(resolve, 100))

    expect(loadSpy).toHaveBeenCalled()
  })
})
