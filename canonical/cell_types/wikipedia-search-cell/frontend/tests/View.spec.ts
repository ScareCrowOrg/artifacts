import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import View from '../View.vue'

// Mock i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key
  })
}))

describe('WikipediaSearchCell View', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('renders the search input', () => {
    const wrapper = mount(View, {
      props: {
        cell: { initial_data: { query: '', language: 'en' } }
      }
    })

    const input = wrapper.find('input[type="text"]')
    expect(input.exists()).toBe(true)
  })

  it('renders the language selector', () => {
    const wrapper = mount(View, {
      props: {
        cell: { initial_data: { query: '', language: 'en' } }
      }
    })

    const select = wrapper.find('select')
    expect(select.exists()).toBe(true)
  })

  it('renders the search button', () => {
    const wrapper = mount(View, {
      props: {
        cell: { initial_data: { query: '', language: 'en' } }
      }
    })

    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)
  })

  it('disables search button when query is empty', () => {
    const wrapper = mount(View, {
      props: {
        cell: { initial_data: { query: '', language: 'en' } }
      }
    })

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('shows empty state when no results', () => {
    const wrapper = mount(View, {
      props: {
        cell: { initial_data: { query: '', language: 'en' } }
      }
    })

    expect(wrapper.text()).toContain('wikipediaSearchCell.emptyState')
  })
})
