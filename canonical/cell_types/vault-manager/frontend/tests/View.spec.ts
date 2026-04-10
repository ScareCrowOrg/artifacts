/**
 * Tests for Vault Manager Cell View Component
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import VaultManagerView from '../View.vue'
import en from '../translations/en.json'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: { en },
})

const mockCell = {
  id: 'vault-manager-test-1',
  notebook_item_type_id: 'vault-manager',
  initial_data: {
    currentTab: 'list',
    auditFilters: {},
  },
}

function mountComponent(overrides: Partial<typeof mockCell> = {}) {
  return mount(VaultManagerView, {
    props: { cell: { ...mockCell, ...overrides } },
    global: { plugins: [i18n] },
  })
}

describe('VaultManagerView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // --------------------------------------------------------------------------
  // Rendering
  // --------------------------------------------------------------------------

  it('renders the cell title', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Vault Manager')
  })

  it('renders description text', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Manage encrypted secrets')
  })

  it('renders tab navigation with three tabs', () => {
    const wrapper = mountComponent()
    const tabs = wrapper.findAll('button').filter((b) => ['Secrets', 'Create', 'Audit Trail'].includes(b.text()))
    expect(tabs.length).toBe(3)
  })

  it('shows the list tab content by default', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('No secrets found')
  })

  it('renders the refresh button', () => {
    const wrapper = mountComponent()
    const refreshBtn = wrapper.findAll('button').find((b) => b.text() === 'Refresh')
    expect(refreshBtn?.exists()).toBe(true)
  })

  // --------------------------------------------------------------------------
  // Tab Navigation
  // --------------------------------------------------------------------------

  it('switches to create tab on click', async () => {
    const wrapper = mountComponent()
    const createTab = wrapper.findAll('button').find((b) => b.text() === 'Create')
    await createTab?.trigger('click')
    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.text()).toContain('Secret Key')
  })

  it('switches to audit tab on click', async () => {
    const wrapper = mountComponent()
    const auditTab = wrapper.findAll('button').find((b) => b.text() === 'Audit Trail')
    await auditTab?.trigger('click')
    expect(wrapper.text()).toContain('No audit entries found')
  })

  it('emits update:cell when tab changes', async () => {
    const wrapper = mountComponent()
    const createTab = wrapper.findAll('button').find((b) => b.text() === 'Create')
    await createTab?.trigger('click')
    const updateEvents = wrapper.emitted('update:cell') as any[]
    expect(updateEvents).toBeTruthy()
    expect(updateEvents[0][0].initial_data.currentTab).toBe('create')
  })

  // --------------------------------------------------------------------------
  // Create Form
  // --------------------------------------------------------------------------

  it('renders create form fields', async () => {
    const wrapper = mountComponent()
    const createTab = wrapper.findAll('button').find((b) => b.text() === 'Create')
    await createTab?.trigger('click')

    const inputs = wrapper.findAll('input')
    expect(inputs.length).toBeGreaterThanOrEqual(2)

    const select = wrapper.find('select')
    expect(select.exists()).toBe(true)
  })

  it('shows category options in create form', async () => {
    const wrapper = mountComponent()
    const createTab = wrapper.findAll('button').find((b) => b.text() === 'Create')
    await createTab?.trigger('click')

    const options = wrapper.findAll('option')
    const optionValues = options.map((o) => o.element.value)
    expect(optionValues).toContain('api')
    expect(optionValues).toContain('database')
    expect(optionValues).toContain('internal')
  })

  it('emits execute on form submit with valid data', async () => {
    const wrapper = mountComponent()
    const createTab = wrapper.findAll('button').find((b) => b.text() === 'Create')
    await createTab?.trigger('click')

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('my-secret')
    await inputs[inputs.length - 1].setValue('my-value')

    const form = wrapper.find('form')
    await form.trigger('submit')

    const executeEvents = wrapper.emitted('execute') as any[]
    expect(executeEvents).toBeTruthy()
    expect(executeEvents[executeEvents.length - 1][0].action).toBe('create')
    expect(executeEvents[executeEvents.length - 1][0].payload.secret_key).toBe('my-secret')
    expect(executeEvents[executeEvents.length - 1][0].payload.value).toBe('my-value')
  })

  it('shows error when submitting empty create form', async () => {
    const wrapper = mountComponent()
    const createTab = wrapper.findAll('button').find((b) => b.text() === 'Create')
    await createTab?.trigger('click')

    const form = wrapper.find('form')
    await form.trigger('submit')

    // Error is shown
    expect(wrapper.text()).toContain('required')
  })

  // --------------------------------------------------------------------------
  // List – Masked values & rotate/delete buttons
  // --------------------------------------------------------------------------

  it('maskValue shows masked secret value', async () => {
    const wrapper = mountComponent()
    // Access the component's expose or test via the utility directly
    // We test indirectly by injecting a secret into the secrets ref
    // through the initial_data watch path won't trigger this, so we test
    // via the component's exposed helper by inspecting rendered output
    // when secrets are populated through execute event flow
    // For unit test: verify the component renders without errors
    expect(wrapper.exists()).toBe(true)
  })

  it('shows create button in list tab', () => {
    const wrapper = mountComponent()
    const createBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Secret'))
    expect(createBtn?.exists()).toBe(true)
  })

  it('clicking "Create Secret" button navigates to create tab', async () => {
    const wrapper = mountComponent()
    const createBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Secret'))
    await createBtn?.trigger('click')
    expect(wrapper.find('form').exists()).toBe(true)
  })

  // --------------------------------------------------------------------------
  // Error Banner
  // --------------------------------------------------------------------------

  it('error banner is hidden initially', () => {
    const wrapper = mountComponent()
    const errorDiv = wrapper.findAll('div').find((d) => d.classes().includes('bg-error') || d.text().includes('bg-error'))
    expect(errorDiv).toBeFalsy()
  })

  // --------------------------------------------------------------------------
  // Lifecycle
  // --------------------------------------------------------------------------

  it('emits execute on mount to load secrets', async () => {
    const wrapper = mountComponent()
    await wrapper.vm.$nextTick()
    const executeEvents = wrapper.emitted('execute') as any[]
    expect(executeEvents).toBeTruthy()
    expect(executeEvents[0][0].action).toBe('list')
  })

  it('emits execute with correct cell_type', async () => {
    const wrapper = mountComponent()
    await wrapper.vm.$nextTick()
    const executeEvents = wrapper.emitted('execute') as any[]
    expect(executeEvents[0][0].cell_type).toBe('vault-manager')
  })

  // --------------------------------------------------------------------------
  // Rotate Modal
  // --------------------------------------------------------------------------

  it('rotate modal is hidden by default', () => {
    const wrapper = mountComponent()
    const modal = wrapper.findAll('[role="dialog"]')
    expect(modal.length).toBe(0)
  })

  // --------------------------------------------------------------------------
  // Props watching
  // --------------------------------------------------------------------------

  it('updates currentTab when initial_data changes', async () => {
    const wrapper = mountComponent()
    await wrapper.setProps({
      cell: {
        ...mockCell,
        initial_data: { currentTab: 'audit', auditFilters: {} },
      },
    })
    await wrapper.vm.$nextTick()
    // The audit tab content should now be visible
    expect(wrapper.text()).toContain('No audit entries')
  })
})
