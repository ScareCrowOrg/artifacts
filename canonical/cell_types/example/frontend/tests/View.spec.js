/**
 * Tests for Example Cell View Component
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ExampleCellView from '../View.vue'

describe('ExampleCellView', () => {
  let wrapper
  const mockCell = {
    id: 'test-cell-123',
    notebook_item_type_id: 'example',
    initial_data: {
      message: 'Test Message',
      counter: 5
    }
  }

  beforeEach(() => {
    wrapper = mount(ExampleCellView, {
      props: {
        cell: mockCell
      }
    })
  })

  it('renders the cell message', () => {
    expect(wrapper.text()).toContain('Test Message')
  })

  it('displays the counter value', () => {
    expect(wrapper.text()).toContain('5')
  })

  it('shows cell ID', () => {
    expect(wrapper.text()).toContain('test-cell-123')
  })

  it('shows cell type', () => {
    expect(wrapper.text()).toContain('example')
  })

  it('increments counter when button clicked', async () => {
    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)

    await button.trigger('click')

    // Check emitted event
    const updateEvents = wrapper.emitted('update:cell')
    expect(updateEvents).toBeTruthy()
    expect(updateEvents.length).toBe(1)

    const emittedCell = updateEvents[0][0]
    expect(emittedCell.initial_data.counter).toBe(6)
  })

  it('emits update when message changes', async () => {
    const input = wrapper.find('input[type="text"]')
    expect(input.exists()).toBe(true)

    await input.setValue('New Message')
    await input.trigger('change')

    const updateEvents = wrapper.emitted('update:cell')
    expect(updateEvents).toBeTruthy()

    const emittedCell = updateEvents[0][0]
    expect(emittedCell.initial_data.message).toBe('New Message')
  })

  it('renders with default values when initial_data is missing', () => {
    const wrapperNoData = mount(ExampleCellView, {
      props: {
        cell: {
          id: 'test-cell-456',
          notebook_item_type_id: 'example',
          initial_data: {}
        }
      }
    })

    expect(wrapperNoData.text()).toContain('Example Cell')
    expect(wrapperNoData.text()).toContain('0')
  })

  it('updates when cell prop changes', async () => {
    await wrapper.setProps({
      cell: {
        ...mockCell,
        initial_data: {
          message: 'Updated Message',
          counter: 10
        }
      }
    })

    // Wait for reactivity
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Updated Message')
    expect(wrapper.text()).toContain('10')
  })
})
