/**
 * Tests for SVG Generator Cell frontend component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import SvgGeneratorView from '../View.vue'

// Mock the i18n plugin
const mockT = (key: string) => key

// Mock the aiChatService
vi.mock('@/services/aiChatService.js', () => ({
  processMessage: vi.fn(),
  prepareConversationHistory: vi.fn()
}))

describe('SVG Generator Cell - View.vue', () => {
  let wrapper: any

  const defaultCell = {
    id: 'test-cell-id',
    notebook_item_type_id: 'svg-generator-cell',
    initial_data: {
      prompt: '',
      generatedSvg: null,
      isGenerating: false,
      error: null
    }
  }

  beforeEach(() => {
    wrapper = mount(SvgGeneratorView, {
      props: {
        cell: defaultCell
      },
      global: {
        mocks: {
          $t: mockT
        }
      }
    })
  })

  describe('Component Rendering', () => {
    it('should render the component', () => {
      expect(wrapper.exists()).toBe(true)
    })

    it('should display the title', () => {
      const title = wrapper.find('h3')
      expect(title.exists()).toBe(true)
    })

    it('should render the prompt textarea', () => {
      const textarea = wrapper.find('textarea')
      expect(textarea.exists()).toBe(true)
    })

    it('should render the generate button', () => {
      const button = wrapper.find('button')
      expect(button.exists()).toBe(true)
    })
  })

  describe('User Interactions', () => {
    it('should update prompt when user types', async () => {
      const textarea = wrapper.find('textarea')
      await textarea.setValue('A blue circle')
      
      expect(wrapper.vm.prompt).toBe('A blue circle')
    })

    it('should disable generate button when prompt is empty', () => {
      const button = wrapper.find('button')
      expect(button.attributes('disabled')).toBeDefined()
    })

    it('should enable generate button when prompt has content', async () => {
      const textarea = wrapper.find('textarea')
      await textarea.setValue('A blue circle')
      await wrapper.vm.$nextTick()
      
      const button = wrapper.find('button')
      expect(button.attributes('disabled')).toBeUndefined()
    })

    it('should disable inputs when generating', async () => {
      wrapper.vm.isGenerating = true
      await wrapper.vm.$nextTick()
      
      const textarea = wrapper.find('textarea')
      expect(textarea.attributes('disabled')).toBeDefined()
    })
  })

  describe('SVG Generation', () => {
    it('should show loading state during generation', async () => {
      wrapper.vm.isGenerating = true
      await wrapper.vm.$nextTick()
      
      const button = wrapper.find('button')
      expect(button.text()).toContain('svgGeneratorCell.generating')
    })

    it('should display error message when generation fails', async () => {
      wrapper.vm.error = 'Test error message'
      await wrapper.vm.$nextTick()
      
      const errorDiv = wrapper.find('.error-section')
      expect(errorDiv.exists()).toBe(true)
      expect(errorDiv.text()).toContain('Test error message')
    })
  })

  describe('SVG Preview', () => {
    it('should not show preview when no SVG is generated', () => {
      const preview = wrapper.find('.svg-preview-section')
      expect(preview.exists()).toBe(false)
    })

    it('should show preview when SVG is generated', async () => {
      wrapper.vm.generatedSvg = '<svg><circle cx="50" cy="50" r="40"/></svg>'
      await wrapper.vm.$nextTick()
      
      const preview = wrapper.find('.svg-preview-section')
      expect(preview.exists()).toBe(true)
    })

    it('should render SVG content', async () => {
      const svgCode = '<svg><circle cx="50" cy="50" r="40"/></svg>'
      wrapper.vm.generatedSvg = svgCode
      await wrapper.vm.$nextTick()
      
      const svgContent = wrapper.find('.svg-content')
      expect(svgContent.exists()).toBe(true)
    })

    it('should show copy and download buttons when SVG exists', async () => {
      wrapper.vm.generatedSvg = '<svg><circle/></svg>'
      await wrapper.vm.$nextTick()
      
      const buttons = wrapper.findAll('button')
      const buttonTexts = buttons.map((b: any) => b.text())
      
      expect(buttonTexts.some((text: string) => text.includes('copySvg'))).toBe(true)
      expect(buttonTexts.some((text: string) => text.includes('downloadSvg'))).toBe(true)
    })
  })

  describe('Code Toggle', () => {
    it('should not show code by default', async () => {
      wrapper.vm.generatedSvg = '<svg><circle/></svg>'
      await wrapper.vm.$nextTick()
      
      const codeBlock = wrapper.find('pre')
      expect(codeBlock.exists()).toBe(false)
    })

    it('should show code when toggled', async () => {
      wrapper.vm.generatedSvg = '<svg><circle/></svg>'
      wrapper.vm.showCode = true
      await wrapper.vm.$nextTick()
      
      const codeBlock = wrapper.find('pre')
      expect(codeBlock.exists()).toBe(true)
      expect(codeBlock.text()).toContain('<svg>')
    })
  })

  describe('Tips Section', () => {
    it('should show tips when no SVG is generated', () => {
      const tips = wrapper.find('.tips-section')
      expect(tips.exists()).toBe(true)
    })

    it('should hide tips when SVG is generated', async () => {
      wrapper.vm.generatedSvg = '<svg><circle/></svg>'
      await wrapper.vm.$nextTick()
      
      const tips = wrapper.find('.tips-section')
      expect(tips.exists()).toBe(false)
    })
  })

  describe('Event Emissions', () => {
    it('should emit update:cell when cell data changes', async () => {
      const textarea = wrapper.find('textarea')
      await textarea.setValue('New prompt')
      
      // Trigger the updateCell function
      wrapper.vm.updateCell()
      
      expect(wrapper.emitted('update:cell')).toBeTruthy()
      const emittedEvent = wrapper.emitted('update:cell')?.[0]?.[0]
      expect(emittedEvent).toHaveProperty('initial_data')
      expect(emittedEvent.initial_data.prompt).toBe('New prompt')
    })
  })

  describe('Accessibility', () => {
    it('should have proper labels for inputs', () => {
      const labels = wrapper.findAll('label')
      expect(labels.length).toBeGreaterThan(0)
    })

    it('should have placeholder text', () => {
      const textarea = wrapper.find('textarea')
      expect(textarea.attributes('placeholder')).toBeDefined()
    })

    it('should disable controls appropriately', async () => {
      wrapper.vm.isGenerating = true
      await wrapper.vm.$nextTick()
      
      const textarea = wrapper.find('textarea')
      const button = wrapper.find('button')
      
      expect(textarea.attributes('disabled')).toBeDefined()
      expect(button.attributes('disabled')).toBeDefined()
    })
  })

  describe('Theme Support', () => {
    it('should have dark mode classes', () => {
      const container = wrapper.find('.svg-generator-cell')
      const classes = container.classes()
      
      expect(classes.some((c: string) => c.includes('dark:'))).toBe(true)
    })
  })
})
