/**
 * Unit tests for Pipeline Monitoring Cell View component
 * 
 * @vitest-environment jsdom
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import View from '../View.vue'
import { useMonitoring } from '../composables/useMonitoring'
import { useHealthChecks } from '../composables/useHealthChecks'
import { useAlerts } from '../composables/useAlerts'

// Mock composables
vi.mock('../composables/useMonitoring')
vi.mock('../composables/useHealthChecks')
vi.mock('../composables/useAlerts')
vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    info: vi.fn(),
    debug: vi.fn(),
    warn: vi.fn(),
    error: vi.fn()
  })
}))

describe('View.vue', () => {
  let wrapper: VueWrapper<any>
  let mockRefreshData: ReturnType<typeof vi.fn>
  let mockStartHealthChecks: ReturnType<typeof vi.fn>
  let mockStopHealthChecks: ReturnType<typeof vi.fn>
  let mockDismissAlert: ReturnType<typeof vi.fn>
  let mockClearAllAlerts: ReturnType<typeof vi.fn>

  const mockPrerequisites = [
    {
      id: 'prereq-1',
      name: 'Test Prerequisite',
      category: 'frontend',
      status: 'healthy',
      criticality: 'critical',
      validation_method: 'Test validation',
      monitoring_available: true,
      details: { test: 'value' },
      timestamp: Date.now()
    }
  ]

  const mockComponents = [
    {
      component: 'Frontend',
      status: 'healthy',
      latency_ms: 15,
      details: {},
      timestamp: Date.now()
    }
  ]

  const mockMetrics = {
    generation_success_rate: 95.5,
    avg_generation_time_ms: 1200,
    active_generations: 2,
    latency_history: [
      { timestamp: Date.now() - 60000, value: 45 },
      { timestamp: Date.now(), value: 50 }
    ],
    quota_history: [
      { timestamp: Date.now() - 60000, value: 20 },
      { timestamp: Date.now(), value: 25 }
    ]
  }

  const mockAlerts = [
    {
      id: 'alert-1',
      severity: 'critical' as const,
      title: 'Test Alert',
      message: 'Test alert message',
      timestamp: Date.now(),
      dismissible: true
    }
  ]

  beforeEach(() => {
    mockRefreshData = vi.fn().mockResolvedValue(undefined)
    mockStartHealthChecks = vi.fn()
    mockStopHealthChecks = vi.fn()
    mockDismissAlert = vi.fn()
    mockClearAllAlerts = vi.fn()

    vi.mocked(useMonitoring).mockReturnValue({
      prerequisites: { value: mockPrerequisites },
      components: { value: mockComponents },
      metrics: { value: mockMetrics },
      refreshData: mockRefreshData,
      isRefreshing: { value: false },
      lastError: { value: null }
    } as any)

    vi.mocked(useHealthChecks).mockReturnValue({
      startHealthChecks: mockStartHealthChecks,
      stopHealthChecks: mockStopHealthChecks,
      isPolling: { value: false },
      pollIntervalSeconds: { value: 30 },
      updateInterval: vi.fn()
    } as any)

    vi.mocked(useAlerts).mockReturnValue({
      alerts: { value: mockAlerts },
      criticalAlerts: { value: mockAlerts },
      warningAlerts: { value: [] },
      infoAlerts: { value: [] },
      alertCount: { value: 1 },
      criticalCount: { value: 1 },
      warningCount: { value: 0 },
      dismissAlert: mockDismissAlert,
      clearAllAlerts: mockClearAllAlerts,
      addAlert: vi.fn(),
      dismissAllBySeverity: vi.fn(),
      hasAlertForComponent: vi.fn(),
      hasAlertForPrerequisite: vi.fn()
    } as any)
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    vi.clearAllMocks()
  })

  describe('Component Mounting', () => {
    it('should mount successfully', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {
              refresh_interval_seconds: 30,
              enable_auto_refresh: true
            }
          }
        }
      })

      expect(wrapper.exists()).toBe(true)
    })

    it('should call refreshData on mount', async () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      await wrapper.vm.$nextTick()
      expect(mockRefreshData).toHaveBeenCalled()
    })

    it('should start health checks if auto-refresh is enabled', async () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {
              enable_auto_refresh: true
            }
          }
        }
      })

      await wrapper.vm.$nextTick()
      expect(mockStartHealthChecks).toHaveBeenCalled()
    })

    it('should not start health checks if auto-refresh is disabled', async () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {
              enable_auto_refresh: false
            }
          }
        }
      })

      await wrapper.vm.$nextTick()
      expect(mockStartHealthChecks).not.toHaveBeenCalled()
    })
  })

  describe('Component Unmounting', () => {
    it('should stop health checks on unmount', async () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      wrapper.unmount()
      expect(mockStopHealthChecks).toHaveBeenCalled()
    })
  })

  describe('Manual Refresh', () => {
    it('should refresh data when refresh button is clicked', async () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      mockRefreshData.mockClear() // Clear initial mount call

      const refreshButton = wrapper.find('button:has(.animate-spin)')
      await refreshButton.trigger('click')

      expect(mockRefreshData).toHaveBeenCalled()
    })

    it('should disable refresh button while refreshing', async () => {
      vi.mocked(useMonitoring).mockReturnValue({
        prerequisites: { value: mockPrerequisites },
        components: { value: mockComponents },
        metrics: { value: mockMetrics },
        refreshData: mockRefreshData,
        isRefreshing: { value: true },
        lastError: { value: null }
      } as any)

      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const refreshButton = wrapper.find('button:has(.animate-spin)')
      expect(refreshButton.attributes('disabled')).toBeDefined()
    })
  })

  describe('Auto-Refresh Toggle', () => {
    it('should toggle auto-refresh when button is clicked', async () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {
              enable_auto_refresh: true
            }
          }
        }
      })

      // Find button by text content
      const buttons = wrapper.findAll('button')
      const toggleButton = buttons.find(btn => btn.text().includes('Auto-Refresh'))
      if (toggleButton) {
        await toggleButton.trigger('click')
      }

      expect(mockStopHealthChecks).toHaveBeenCalled()
    })

    it('should emit update:cell event when toggling auto-refresh', async () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {
              enable_auto_refresh: true
            }
          }
        }
      })

      // Find button by text content
      const buttons = wrapper.findAll('button')
      const toggleButton = buttons.find(btn => btn.text().includes('Auto-Refresh'))
      if (toggleButton) {
        await toggleButton.trigger('click')
      }

      expect(wrapper.emitted('update:cell')).toBeTruthy()
    })
  })

  describe('Statistics Display', () => {
    it('should display correct prerequisite count', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const statsCard = wrapper.find('.stat-card')
      expect(statsCard.text()).toContain('1/1')
    })

    it('should display generation success rate', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      expect(wrapper.text()).toContain('95.5%')
    })

    it('should display average generation time', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      expect(wrapper.text()).toContain('1200ms')
    })

    it('should display active generations count', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      expect(wrapper.text()).toContain('2')
    })
  })

  describe('Alert Banner', () => {
    it('should show alert banner when critical alerts exist', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const alertBanner = wrapper.findComponent({ name: 'AlertBanner' })
      expect(alertBanner.exists()).toBe(true)
    })

    it('should not show alert banner when no critical alerts', () => {
      vi.mocked(useAlerts).mockReturnValue({
        alerts: { value: [] },
        criticalAlerts: { value: [] },
        warningAlerts: { value: [] },
        infoAlerts: { value: [] },
        alertCount: { value: 0 },
        criticalCount: { value: 0 },
        warningCount: { value: 0 },
        dismissAlert: mockDismissAlert,
        clearAllAlerts: mockClearAllAlerts,
        addAlert: vi.fn(),
        dismissAllBySeverity: vi.fn(),
        hasAlertForComponent: vi.fn(),
        hasAlertForPrerequisite: vi.fn()
      } as any)

      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const alertBanner = wrapper.findComponent({ name: 'AlertBanner' })
      expect(alertBanner.exists()).toBe(false)
    })
  })

  describe('Component Health Indicators', () => {
    it('should render health indicator for each component', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const healthIndicators = wrapper.findAllComponents({ name: 'ComponentHealthIndicator' })
      expect(healthIndicators).toHaveLength(1)
    })
  })

  describe('Prerequisite Cards', () => {
    it('should render prerequisite card for each prerequisite', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const prerequisiteCards = wrapper.findAllComponents({ name: 'PrerequisiteCard' })
      expect(prerequisiteCards).toHaveLength(1)
    })

    it('should group prerequisites by category', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const categorySection = wrapper.find('.category-section')
      expect(categorySection.exists()).toBe(true)
      expect(categorySection.text()).toContain('Frontend')
    })
  })

  describe('Metrics Charts', () => {
    it('should render latency chart', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const charts = wrapper.findAllComponents({ name: 'MetricsChart' })
      expect(charts.length).toBeGreaterThan(0)
    })

    it('should render quota chart', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const charts = wrapper.findAllComponents({ name: 'MetricsChart' })
      expect(charts.length).toBe(2)
    })
  })

  describe('Quick Actions', () => {
    it('should render quick actions component', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const quickActions = wrapper.findComponent({ name: 'QuickActions' })
      expect(quickActions.exists()).toBe(true)
    })

    it('should have three available actions', () => {
      wrapper = mount(View, {
        props: {
          cell: {
            initial_data: {}
          }
        }
      })

      const quickActions = wrapper.findComponent({ name: 'QuickActions' })
      expect(quickActions.props('availableActions')).toHaveLength(3)
    })
  })
})
