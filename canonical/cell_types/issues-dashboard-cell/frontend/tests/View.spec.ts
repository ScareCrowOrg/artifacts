/**
 * @file View.spec.ts
 * @description Unit tests for Issues Dashboard View component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import View from '../View.vue'
import { useIssuesStore } from '../stores/issuesStore'
import { usePermissionsStore } from '@/stores/permissions'

// Mock child components
vi.mock('../components/IssueStats.vue', () => ({
  default: { name: 'IssueStats', template: '<div data-testid="issue-stats"></div>' }
}))
vi.mock('../components/IssueFilters.vue', () => ({
  default: { name: 'IssueFilters', template: '<div data-testid="issue-filters"></div>' }
}))
vi.mock('../components/IssueList.vue', () => ({
  default: { name: 'IssueList', template: '<div data-testid="issue-list"></div>' }
}))
vi.mock('../components/Pagination.vue', () => ({
  default: { name: 'Pagination', template: '<div data-testid="pagination"></div>' }
}))
vi.mock('../components/IngestForm.vue', () => ({
  default: { name: 'IngestForm', template: '<div data-testid="ingest-form"></div>' }
}))
vi.mock('../components/CreateCellForm.vue', () => ({
  default: { name: 'CreateCellForm', template: '<div data-testid="create-cell-form"></div>' }
}))
vi.mock('../components/PipelineActivityFeed.vue', () => ({
  default: { name: 'PipelineActivityFeed', template: '<div data-testid="pipeline-feed"></div>' }
}))
vi.mock('../components/IssueDetails.vue', () => ({
  default: { name: 'IssueDetails', template: '<div data-testid="issue-details"></div>' }
}))

// Mock logger
vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn()
  })
}))

describe('Issues Dashboard View', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })

  it('should render the dashboard title', () => {
    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    expect(wrapper.text()).toContain('issues.dashboard.title')
  })

  it('should emit close event when close button is clicked', async () => {
    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    const closeButton = wrapper.find('button[aria-label="issues.dashboard.closeAriaLabel"]')
    await closeButton.trigger('click')

    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('should show read-only warning without write permission', () => {
    const permissionsStore = usePermissionsStore()
    vi.spyOn(permissionsStore, 'hasPermission').mockReturnValue(false)

    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    expect(wrapper.text()).toContain('issues.dashboard.readOnlyMode')
  })

  it('should not show read-only warning with write permission', () => {
    const permissionsStore = usePermissionsStore()
    vi.spyOn(permissionsStore, 'hasPermission').mockReturnValue(true)

    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    expect(wrapper.text()).not.toContain('issues.dashboard.readOnlyMode')
  })

  it('should render IssueStats component', () => {
    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    expect(wrapper.find('[data-testid="issue-stats"]').exists()).toBe(true)
  })

  it('should render IssueFilters component', () => {
    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    expect(wrapper.find('[data-testid="issue-filters"]').exists()).toBe(true)
  })

  it('should render IssueList component', () => {
    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    expect(wrapper.find('[data-testid="issue-list"]').exists()).toBe(true)
  })

  it('should call store actions on mount', () => {
    const issuesStore = useIssuesStore()
    const loadIssuesSpy = vi.spyOn(issuesStore, 'loadIssues')
    const loadMonitoringStatusSpy = vi.spyOn(issuesStore, 'loadMonitoringStatus')
    const loadProcessingStatusSpy = vi.spyOn(issuesStore, 'loadProcessingStatus')
    const loadNotebookItemTypesSpy = vi.spyOn(issuesStore, 'loadNotebookItemTypes')
    const connectSSESpy = vi.spyOn(issuesStore, 'connectSSE')
    const startPipelineStreamSpy = vi.spyOn(issuesStore, 'startPipelineStream')

    mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    expect(loadIssuesSpy).toHaveBeenCalled()
    expect(loadMonitoringStatusSpy).toHaveBeenCalled()
    expect(loadProcessingStatusSpy).toHaveBeenCalled()
    expect(loadNotebookItemTypesSpy).toHaveBeenCalled()
    expect(connectSSESpy).toHaveBeenCalled()
    expect(startPipelineStreamSpy).toHaveBeenCalled()
  })

  it('should show error message when error exists in store', () => {
    const issuesStore = useIssuesStore()
    issuesStore.error = 'Test error message'

    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    expect(wrapper.text()).toContain('Test error message')
  })

  it('should clear error when close button is clicked', async () => {
    const issuesStore = useIssuesStore()
    issuesStore.error = 'Test error'

    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    const errorCloseButton = wrapper.findAll('button').find(btn => 
      btn.element.textContent?.trim() === '✕'
    )
    
    if (errorCloseButton) {
      await errorCloseButton.trigger('click')
      expect(issuesStore.error).toBeNull()
    }
  })

  it('should show monitoring status when active', () => {
    const issuesStore = useIssuesStore()
    issuesStore.monitoringStatus = {
      active: true,
      polling_interval: 5,
      max_concurrent_cells: 2,
      task_running: true
    }

    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string, params: any) => `${key} ${JSON.stringify(params)}`
        }
      }
    })

    expect(wrapper.text()).toContain('issues.dashboard.monitoringActive')
  })

  it('should show processing paused status', () => {
    const issuesStore = useIssuesStore()
    issuesStore.processingStatus = { paused: true }

    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    expect(wrapper.text()).toContain('issues.dashboard.processingPaused')
  })

  it('should not show IngestForm without write permission', () => {
    const permissionsStore = usePermissionsStore()
    vi.spyOn(permissionsStore, 'hasPermission').mockReturnValue(false)

    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    wrapper.vm.showIngestForm = true
    wrapper.vm.$forceUpdate()

    expect(wrapper.find('[data-testid="ingest-form"]').exists()).toBe(false)
  })

  it('should show IngestForm with write permission', async () => {
    const permissionsStore = usePermissionsStore()
    vi.spyOn(permissionsStore, 'hasPermission').mockReturnValue(true)

    const wrapper = mount(View, {
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        }
      }
    })

    // Set showIngestForm to true
    await wrapper.setData({ showIngestForm: true })

    // The form should now be visible
    expect(wrapper.find('[data-testid="ingest-form"]').exists()).toBe(true)
  })
})
