/**
 * @file View.spec.ts
 * @description Component tests for Settings Panel View
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import View from '../View.vue'
import { SettingsPanelCell } from '../SettingsPanelCell'

// Mock authStore
const mockAuthStore = {
  hasPermission: vi.fn()
}

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore
}))

// Mock i18n
const mockI18n = {
  t: (key: string) => key
}

describe('Settings Panel View', () => {
  let cellInstance: SettingsPanelCell

  beforeEach(() => {
    setActivePinia(createPinia())
    cellInstance = new SettingsPanelCell()
    mockAuthStore.hasPermission.mockReset()
  })

  it('should render user settings tab by default', async () => {
    mockAuthStore.hasPermission.mockResolvedValue(false)
    
    const wrapper = mount(View, {
      props: {
        cellInstance
      },
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.settings-panel-cell').exists()).toBe(true)
    expect(wrapper.text()).toContain('Settings')
  })

  it('should show only user settings tab when user lacks admin permission', async () => {
    mockAuthStore.hasPermission.mockResolvedValue(false)
    
    const wrapper = mount(View, {
      props: {
        cellInstance
      },
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))

    const tabs = wrapper.findAll('button')
    const userTab = tabs.find(tab => tab.text().includes('settings.userTab'))
    const adminTab = tabs.find(tab => tab.text().includes('settings.adminTab'))

    expect(userTab).toBeDefined()
    expect(adminTab).toBeUndefined()
  })

  it('should show both tabs when user has admin permission', async () => {
    mockAuthStore.hasPermission.mockResolvedValue(true)
    
    const wrapper = mount(View, {
      props: {
        cellInstance
      },
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))

    const tabs = wrapper.findAll('button')
    const userTab = tabs.find(tab => tab.text().includes('settings.userTab'))
    const adminTab = tabs.find(tab => tab.text().includes('settings.adminTab'))

    expect(userTab).toBeDefined()
    expect(adminTab).toBeDefined()
  })

  it('should switch tabs on click', async () => {
    mockAuthStore.hasPermission.mockResolvedValue(true)
    
    const wrapper = mount(View, {
      props: {
        cellInstance
      },
      global: {
        mocks: {
          $t: mockI18n.t
        }
      }
    })

    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))

    const tabs = wrapper.findAll('button')
    const adminTab = tabs.find(tab => tab.text().includes('settings.adminTab'))

    if (adminTab) {
      await adminTab.trigger('click')
      await wrapper.vm.$nextTick()

      // Admin tab should now be active
      expect(wrapper.vm.activeTab).toBe('admin')
    }
  })
})
