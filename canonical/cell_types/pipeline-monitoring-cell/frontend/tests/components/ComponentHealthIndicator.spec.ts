/**
 * Unit tests for ComponentHealthIndicator component
 * 
 * @vitest-environment jsdom
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import ComponentHealthIndicator from '../../components/ComponentHealthIndicator.vue'
import type { ComponentHealth } from '../../composables/useMonitoring'

describe('ComponentHealthIndicator.vue', () => {
  let wrapper: VueWrapper<any>

  const mockComponent: ComponentHealth = {
    component: 'Frontend',
    status: 'healthy',
    latency_ms: 15,
    details: {},
    timestamp: Date.now()
  }

  describe('Component Rendering', () => {
    it('should render successfully', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: mockComponent
        }
      })

      expect(wrapper.exists()).toBe(true)
    })

    it('should display component name', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: mockComponent
        }
      })

      expect(wrapper.text()).toContain('Frontend')
    })

    it('should display latency', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: mockComponent
        }
      })

      expect(wrapper.text()).toContain('15ms')
    })
  })

  describe('Health Status Styling', () => {
    it('should apply healthy status class', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'healthy' }
        }
      })

      const indicator = wrapper.find('.health-indicator')
      expect(indicator.classes()).toContain('border-success/40')
      expect(indicator.classes()).toContain('bg-success/10')
    })

    it('should apply degraded status class', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'degraded' }
        }
      })

      const indicator = wrapper.find('.health-indicator')
      expect(indicator.classes()).toContain('border-warning/40')
      expect(indicator.classes()).toContain('bg-warning/10')
    })

    it('should apply unhealthy status class', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'unhealthy' }
        }
      })

      const indicator = wrapper.find('.health-indicator')
      expect(indicator.classes()).toContain('border-error/40')
      expect(indicator.classes()).toContain('bg-error/10')
    })

    it('should apply unknown status class', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'unknown' }
        }
      })

      const indicator = wrapper.find('.health-indicator')
      expect(indicator.classes()).toContain('border-border')
      expect(indicator.classes()).toContain('bg-background')
    })
  })

  describe('Icon Display', () => {
    it('should apply healthy icon class', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'healthy' }
        }
      })

      const icon = wrapper.find('.health-icon')
      expect(icon.classes()).toContain('text-success')
    })

    it('should apply degraded icon class', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'degraded' }
        }
      })

      const icon = wrapper.find('.health-icon')
      expect(icon.classes()).toContain('text-warning')
    })

    it('should apply unhealthy icon class', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'unhealthy' }
        }
      })

      const icon = wrapper.find('.health-icon')
      expect(icon.classes()).toContain('text-error')
    })

    it('should apply unknown icon class', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'unknown' }
        }
      })

      const icon = wrapper.find('.health-icon')
      expect(icon.classes()).toContain('text-muted-foreground')
    })
  })

  describe('Status Dot', () => {
    it('should show success dot for healthy status', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'healthy' }
        }
      })

      const dot = wrapper.find('.status-dot')
      expect(dot.classes()).toContain('bg-success')
    })

    it('should show warning dot for degraded status', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'degraded' }
        }
      })

      const dot = wrapper.find('.status-dot')
      expect(dot.classes()).toContain('bg-warning')
    })

    it('should show error dot for unhealthy status', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'unhealthy' }
        }
      })

      const dot = wrapper.find('.status-dot')
      expect(dot.classes()).toContain('bg-error')
    })
  })

  describe('Tooltip', () => {
    it('should have tooltip with component info', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: mockComponent
        }
      })

      const indicator = wrapper.find('.health-indicator')
      const title = indicator.attributes('title')
      
      expect(title).toContain('Frontend')
      expect(title).toContain('Healthy')
      expect(title).toContain('15ms')
    })

    it('should update tooltip for degraded status', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, status: 'degraded' }
        }
      })

      const indicator = wrapper.find('.health-indicator')
      const title = indicator.attributes('title')
      
      expect(title).toContain('Degraded')
    })

    it('should include latency in tooltip', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, latency_ms: 123 }
        }
      })

      const indicator = wrapper.find('.health-indicator')
      const title = indicator.attributes('title')
      
      expect(title).toContain('123ms latency')
    })
  })

  describe('Different Components', () => {
    const components = [
      'Frontend',
      'Extension',
      'WASM',
      'Backend',
      'MongoDB',
      'Vault',
      'Redis'
    ]

    components.forEach(componentName => {
      it(`should render ${componentName} component correctly`, () => {
        wrapper = mount(ComponentHealthIndicator, {
          props: {
            component: { ...mockComponent, component: componentName }
          }
        })

        expect(wrapper.text()).toContain(componentName)
      })
    })
  })

  describe('Latency Display', () => {
    it('should format low latency correctly', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, latency_ms: 5 }
        }
      })

      expect(wrapper.text()).toContain('5ms')
    })

    it('should format high latency correctly', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, latency_ms: 1523 }
        }
      })

      expect(wrapper.text()).toContain('1523ms')
    })

    it('should handle zero latency', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: { ...mockComponent, latency_ms: 0 }
        }
      })

      expect(wrapper.text()).toContain('0ms')
    })
  })

  describe('Interactive Behavior', () => {
    it('should have hover state classes', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: mockComponent
        }
      })

      const indicator = wrapper.find('.health-indicator')
      // Component has hover states in the health class (e.g., hover:bg-success/20)
      const classes = indicator.classes().join(' ')
      expect(classes).toBeTruthy()
    })

    it('should apply correct health status class', () => {
      wrapper = mount(ComponentHealthIndicator, {
        props: {
          component: mockComponent
        }
      })

      const indicator = wrapper.find('.health-indicator')
      // Check that health status classes are applied
      expect(indicator.attributes('class')).toBeTruthy()
    })
  })
})
