/**
 * Unit tests for Log Toggle Cell Vue component
 * @vitest-environment happy-dom
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import LogToggleCell from '../View.vue'

describe('LogToggleCell', () => {
  let wrapper: any

  const defaultProps = {
    cell: {
      initial_data: {
        enabled_namespaces: [],
        debug_pattern: ''
      }
    }
  }

  beforeEach(() => {
    wrapper = mount(LogToggleCell, {
      props: defaultProps
    })
  })

  describe('Rendering', () => {
    it('should render the component', () => {
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.log-toggle-cell').exists()).toBe(true)
    })

    it('should display the title', () => {
      expect(wrapper.text()).toContain('Log Toggle Control')
    })

    it('should display description text', () => {
      expect(wrapper.text()).toContain('Temporarily enable/disable log namespaces')
    })

    it('should render action buttons', () => {
      expect(wrapper.find('button').text()).toBeTruthy()
      const buttons = wrapper.findAll('button')
      expect(buttons.length).toBeGreaterThan(0)
    })

    it('should render search input', () => {
      const searchInput = wrapper.find('input[type="text"]')
      expect(searchInput.exists()).toBe(true)
      expect(searchInput.attributes('placeholder')).toContain('Search')
    })
  })

  describe('Namespace List', () => {
    it('should display available namespaces', () => {
      const namespaces = wrapper.findAll('input[type="checkbox"]')
      expect(namespaces.length).toBeGreaterThan(0)
    })

    it('should have checkboxes for each namespace', () => {
      const checkboxes = wrapper.findAll('input[type="checkbox"]')
      expect(checkboxes.length).toBeGreaterThan(0)
      
      checkboxes.forEach((checkbox: any) => {
        expect(checkbox.attributes('type')).toBe('checkbox')
      })
    })
  })

  describe('Search Functionality', () => {
    it('should filter namespaces based on search', async () => {
      const searchInput = wrapper.find('input[type="text"]')
      
      // Get initial count
      const initialCheckboxes = wrapper.findAll('input[type="checkbox"]')
      const initialCount = initialCheckboxes.length
      
      // Enter search term
      await searchInput.setValue('auth')
      await wrapper.vm.$nextTick()
      
      // Check filtered count (should be less than or equal to initial)
      const filteredCheckboxes = wrapper.findAll('input[type="checkbox"]')
      expect(filteredCheckboxes.length).toBeLessThanOrEqual(initialCount)
    })

    it('should show empty state when no matches', async () => {
      const searchInput = wrapper.find('input[type="text"]')
      
      // Search for something that doesn't exist
      await searchInput.setValue('nonexistentnamespace123')
      await wrapper.vm.$nextTick()
      
      // Should show no results message
      expect(wrapper.text()).toContain('No namespaces match')
    })
  })

  describe('Namespace Toggle', () => {
    it('should toggle namespace on checkbox click', async () => {
      const checkbox = wrapper.find('input[type="checkbox"]')
      
      const initialChecked = checkbox.element.checked
      
      await checkbox.trigger('change')
      await wrapper.vm.$nextTick()
      
      // State should have changed
      const newChecked = checkbox.element.checked
      expect(newChecked).not.toBe(initialChecked)
    })
  })

  describe('Bulk Actions', () => {
    it('should have Enable All button', () => {
      const buttons = wrapper.findAll('button')
      const enableAllButton = buttons.find((btn: any) => btn.text().includes('Enable All'))
      expect(enableAllButton).toBeTruthy()
    })

    it('should have Disable All button', () => {
      const buttons = wrapper.findAll('button')
      const disableAllButton = buttons.find((btn: any) => btn.text().includes('Disable All'))
      expect(disableAllButton).toBeTruthy()
    })

    it('should have Apply Changes button', () => {
      const buttons = wrapper.findAll('button')
      const applyButton = buttons.find((btn: any) => btn.text().includes('Apply Changes'))
      expect(applyButton).toBeTruthy()
    })
  })

  describe('Active Count Display', () => {
    it('should not show active count when no namespaces enabled', () => {
      const activeCount = wrapper.find('.bg-success')
      // Should not exist when count is 0
      expect(activeCount.exists()).toBe(false)
    })
  })

  describe('Current Pattern Display', () => {
    it('should display current DEBUG pattern', () => {
      expect(wrapper.text()).toContain('Current DEBUG Pattern')
    })

    it('should show "none" when no namespaces enabled', () => {
      expect(wrapper.text()).toContain('(none - all logs disabled)')
    })
  })

  describe('Props Integration', () => {
    it('should accept and display initial enabled namespaces', async () => {
      const wrapperWithData = mount(LogToggleCell, {
        props: {
          cell: {
            initial_data: {
              enabled_namespaces: ['auth', 'api'],
              debug_pattern: 'auth,api'
            }
          }
        }
      })

      await wrapperWithData.vm.$nextTick()

      // Should display the pattern
      expect(wrapperWithData.text()).toContain('auth,api')
    })
  })

  describe('Event Emission', () => {
    it('should emit update:cell event on apply changes', async () => {
      // First enable a namespace
      const checkbox = wrapper.find('input[type="checkbox"]')
      await checkbox.trigger('change')
      await wrapper.vm.$nextTick()

      // Find and click apply button
      const buttons = wrapper.findAll('button')
      const applyButton = buttons.find((btn: any) => btn.text().includes('Apply Changes'))
      
      await applyButton.trigger('click')
      await wrapper.vm.$nextTick()

      // Check if event was emitted
      expect(wrapper.emitted('update:cell')).toBeTruthy()
    })
  })

  describe('TypeScript Type Safety', () => {
    it('should handle missing initial_data gracefully', () => {
      const wrapperNoData = mount(LogToggleCell, {
        props: {
          cell: {}
        }
      })

      expect(wrapperNoData.exists()).toBe(true)
      // Should default to empty state
      expect(wrapperNoData.text()).toContain('(none - all logs disabled)')
    })
  })
})
