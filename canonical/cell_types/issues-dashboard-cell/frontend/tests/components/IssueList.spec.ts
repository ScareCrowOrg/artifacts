/**
 * @file IssueList.spec.ts
 * @description Unit tests for IssueList component
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import IssueList from '../../components/IssueList.vue'
import { useIssuesStore } from '../../stores/issuesStore'

describe('IssueList', () => {
  let pinia: ReturnType<typeof createPinia>
  let issuesStore: ReturnType<typeof useIssuesStore>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    issuesStore = useIssuesStore()
  })

  it('should show loading state when isLoading is true', () => {
    issuesStore.isLoading = true
    issuesStore.filteredIssues = []

    const wrapper = mount(IssueList, {
      props: { hasWritePermission: true },
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        },
        stubs: {
          IssueCard: {
            name: 'IssueCard',
            props: ['cell', 'isSelected'],
            template: '<div data-testid="issue-card" :data-cell-id="cell?.id"></div>'
          }
        }
      }
    })

    expect(wrapper.text()).toContain('issues.list.loading')
  })

  it('should show empty state when no issues are found', () => {
    issuesStore.isLoading = false
    issuesStore.filteredIssues = []

    const wrapper = mount(IssueList, {
      props: { hasWritePermission: true },
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        },
        stubs: {
          IssueCard: {
            name: 'IssueCard',
            props: ['cell', 'isSelected'],
            template: '<div data-testid="issue-card" :data-cell-id="cell?.id"></div>'
          }
        }
      }
    })

    expect(wrapper.text()).toContain('issues.list.noCellsFound')
  })

  it('should render IssueCard for each issue', () => {
    issuesStore.isLoading = false
    issuesStore.filteredIssues = [
      { id: '1', title: 'Issue 1', status: 'pending' },
      { id: '2', title: 'Issue 2', status: 'completed' },
      { id: '3', title: 'Issue 3', status: 'error' }
    ]

    const wrapper = mount(IssueList, {
      props: { hasWritePermission: true },
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        },
        stubs: {
          IssueCard: {
            name: 'IssueCard',
            props: ['cell', 'isSelected'],
            template: '<div data-testid="issue-card" :data-cell-id="cell?.id"></div>'
          }
        }
      }
    })

    const cards = wrapper.findAll('[data-testid="issue-card"]')
    expect(cards).toHaveLength(3)
    expect(cards[0].attributes('data-cell-id')).toBe('1')
    expect(cards[1].attributes('data-cell-id')).toBe('2')
    expect(cards[2].attributes('data-cell-id')).toBe('3')
  })

  it('should pass hasWritePermission prop to component', () => {
    issuesStore.isLoading = false
    issuesStore.filteredIssues = [
      { id: '1', title: 'Issue 1', status: 'pending' }
    ]

    const wrapper = mount(IssueList, {
      props: { hasWritePermission: false },
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        },
        stubs: {
          IssueCard: {
            name: 'IssueCard',
            props: ['cell', 'isSelected'],
            template: '<div data-testid="issue-card" :data-cell-id="cell?.id"></div>'
          }
        }
      }
    })

    expect(wrapper.props('hasWritePermission')).toBe(false)
  })

  it('should render with custom scrollbar styles', () => {
    issuesStore.isLoading = false
    issuesStore.filteredIssues = [
      { id: '1', title: 'Issue 1', status: 'pending' }
    ]

    const wrapper = mount(IssueList, {
      props: { hasWritePermission: true },
      global: {
        plugins: [pinia],
        mocks: {
          $t: (key: string) => key
        },
        stubs: {
          IssueCard: {
            name: 'IssueCard',
            props: ['cell', 'isSelected'],
            template: '<div data-testid="issue-card" :data-cell-id="cell?.id"></div>'
          }
        }
      }
    })

    const container = wrapper.find('.overflow-y-auto')
    expect(container.exists()).toBe(true)
  })
})
