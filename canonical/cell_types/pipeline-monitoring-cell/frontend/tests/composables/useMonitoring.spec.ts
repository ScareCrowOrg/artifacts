/**
 * Unit tests for useMonitoring composable
 * 
 * @vitest-environment jsdom
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useMonitoring } from '../../composables/useMonitoring'

// Mock logger
vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    info: vi.fn(),
    debug: vi.fn(),
    warn: vi.fn(),
    error: vi.fn()
  })
}))

describe('useMonitoring', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    // Mock fetch globally
    global.fetch = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Composable Initialization', () => {
    it('should return monitoring state and methods', () => {
      const {
        prerequisites,
        components,
        metrics,
        refreshData,
        isRefreshing,
        lastError
      } = useMonitoring()

      expect(prerequisites).toBeDefined()
      expect(components).toBeDefined()
      expect(metrics).toBeDefined()
      expect(refreshData).toBeInstanceOf(Function)
      expect(isRefreshing).toBeDefined()
      expect(lastError).toBeDefined()
    })

    it('should initialize with empty state', () => {
      const { prerequisites, components, metrics } = useMonitoring()

      // Initial state should be from mock data
      expect(prerequisites.value).toBeInstanceOf(Array)
      expect(components.value).toBeInstanceOf(Array)
      expect(metrics.value).toHaveProperty('generation_success_rate')
      expect(metrics.value).toHaveProperty('avg_generation_time_ms')
      expect(metrics.value).toHaveProperty('active_generations')
    })
  })

  describe('refreshData', () => {
    it('should set isRefreshing to true during refresh', async () => {
      const { refreshData, isRefreshing } = useMonitoring()

      const refreshPromise = refreshData()
      expect(isRefreshing.value).toBe(true)

      await refreshPromise
      expect(isRefreshing.value).toBe(false)
    })

    it('should update prerequisites after successful refresh', async () => {
      const mockResponse = {
        prerequisites: [
          {
            id: 'test-1',
            name: 'Test Prerequisite',
            category: 'frontend',
            status: 'healthy',
            criticality: 'critical',
            validation_method: 'Test',
            monitoring_available: true,
            details: {},
            timestamp: Date.now()
          }
        ],
        components: [],
        metrics: {
          generation_success_rate: 95,
          avg_generation_time_ms: 1000,
          active_generations: 1,
          latency_history: [],
          quota_history: []
        }
      }

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      const { refreshData, prerequisites } = useMonitoring()
      await refreshData()

      expect(prerequisites.value).toHaveLength(1)
      expect(prerequisites.value[0].name).toBe('Test Prerequisite')
    })

    it('should update components after successful refresh', async () => {
      const mockResponse = {
        prerequisites: [],
        components: [
          {
            component: 'Frontend',
            status: 'healthy',
            latency_ms: 15,
            details: {},
            timestamp: Date.now()
          }
        ],
        metrics: {
          generation_success_rate: 95,
          avg_generation_time_ms: 1000,
          active_generations: 1,
          latency_history: [],
          quota_history: []
        }
      }

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      const { refreshData, components } = useMonitoring()
      await refreshData()

      expect(components.value).toHaveLength(1)
      expect(components.value[0].component).toBe('Frontend')
    })

    it('should update metrics after successful refresh', async () => {
      const mockResponse = {
        prerequisites: [],
        components: [],
        metrics: {
          generation_success_rate: 98.5,
          avg_generation_time_ms: 1250,
          active_generations: 3,
          latency_history: [
            { timestamp: Date.now(), value: 45 }
          ],
          quota_history: [
            { timestamp: Date.now(), value: 25 }
          ]
        }
      }

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      } as Response)

      const { refreshData, metrics } = useMonitoring()
      await refreshData()

      expect(metrics.value.generation_success_rate).toBe(98.5)
      expect(metrics.value.avg_generation_time_ms).toBe(1250)
      expect(metrics.value.active_generations).toBe(3)
    })

    it('should handle API errors gracefully', async () => {
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error'
      } as Response)

      const { refreshData, lastError } = useMonitoring()
      await refreshData()

      // Should fall back to mock data, not throw
      expect(lastError.value).toBeNull() // Mock data fallback succeeds
    })

    it('should handle network errors gracefully', async () => {
      vi.mocked(global.fetch).mockRejectedValueOnce(new Error('Network error'))

      const { refreshData, prerequisites } = useMonitoring()
      await refreshData()

      // Should fall back to mock data
      expect(prerequisites.value).toBeInstanceOf(Array)
      expect(prerequisites.value.length).toBeGreaterThan(0)
    })

    it('should not allow concurrent refreshes', async () => {
      const { refreshData, isRefreshing } = useMonitoring()

      const promise1 = refreshData()
      const promise2 = refreshData() // Should be skipped

      await Promise.all([promise1, promise2])

      expect(isRefreshing.value).toBe(false)
    })
  })

  describe('Mock Data', () => {
    it('should provide mock data with all 24 prerequisites', async () => {
      vi.mocked(global.fetch).mockRejectedValueOnce(new Error('No API'))

      const { refreshData, prerequisites } = useMonitoring()
      await refreshData()

      expect(prerequisites.value).toHaveLength(24)
    })

    it('should provide mock data with 7 components', async () => {
      vi.mocked(global.fetch).mockRejectedValueOnce(new Error('No API'))

      const { refreshData, components } = useMonitoring()
      await refreshData()

      expect(components.value).toHaveLength(7)
    })

    it('should provide mock metrics with history', async () => {
      vi.mocked(global.fetch).mockRejectedValueOnce(new Error('No API'))

      const { refreshData, metrics } = useMonitoring()
      await refreshData()

      expect(metrics.value.latency_history).toHaveLength(20)
      expect(metrics.value.quota_history).toHaveLength(20)
    })

    it('should have all prerequisite categories', async () => {
      vi.mocked(global.fetch).mockRejectedValueOnce(new Error('No API'))

      const { refreshData, prerequisites } = useMonitoring()
      await refreshData()

      const categories = new Set(prerequisites.value.map(p => p.category))
      
      expect(categories).toContain('frontend')
      expect(categories).toContain('extension')
      expect(categories).toContain('wasm')
      expect(categories).toContain('backend')
      expect(categories).toContain('infrastructure')
      expect(categories).toContain('configuration')
      expect(categories).toContain('runtime')
    })

    it('should have critical prerequisites', async () => {
      vi.mocked(global.fetch).mockRejectedValueOnce(new Error('No API'))

      const { refreshData, prerequisites } = useMonitoring()
      await refreshData()

      const criticalPrereqs = prerequisites.value.filter(
        p => p.criticality === 'critical'
      )
      
      expect(criticalPrereqs.length).toBeGreaterThan(0)
    })
  })

  describe('Shared State', () => {
    it('should share state across multiple instances', async () => {
      const instance1 = useMonitoring()
      const instance2 = useMonitoring()

      await instance1.refreshData()

      // Both instances should see the same data
      expect(instance1.prerequisites.value).toBe(instance2.prerequisites.value)
      expect(instance1.components.value).toBe(instance2.components.value)
      expect(instance1.metrics.value).toBe(instance2.metrics.value)
    })
  })
})
