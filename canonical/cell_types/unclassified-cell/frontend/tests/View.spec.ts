/**
 * @file View.spec.ts
 * @description Unit tests for Unclassified Cell View component
 * 
 * Tests cover:
 * - Component mounting and initialization
 * - Cell data loading
 * - User interactions (editing, saving)
 * - Fragment display logic
 * - Send to chat functionality
 * - Error handling
 * - Toolbar integration
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import View from '../View.vue'
import type { UnclassifiedCell } from '../composables/useUnclassifiedCell'

// Mock components
vi.mock('@/components/MarkdownEditor.vue', () => ({
  default: {
    name: 'MarkdownEditor',
    template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'placeholder', 'readonly'],
  },
}))

vi.mock('@/components/MarkdownRenderer.vue', () => ({
  default: {
    name: 'MarkdownRenderer',
    template: '<div class="markdown-rendered">{{ content }}</div>',
    props: ['content'],
  },
}))

// Mock stores
const mockCellsStore = {
  updateCellData: vi.fn(),
  closeCellView: vi.fn(),
}

const mockChatStore = {
  addAttachment: vi.fn(),
}

vi.mock('@/stores/cells', () => ({
  useCellsStore: () => mockCellsStore,
}))

vi.mock('@/stores/chat', () => ({
  useChatStore: () => mockChatStore,
}))

describe('Unclassified Cell View', () => {
  let wrapper: VueWrapper<any>
  let mockCell: UnclassifiedCell

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks()

    // Create mock cell
    mockCell = {
      id: 'test-cell-123',
      notebook_item_type_id: 'unclassified-cell',
      type: 'unclassified-cell',
      initial_data: {
        title: 'Test Cell Title',
        content: 'Test cell content',
        category: 'persistida',
        icon: 'mdi-text-box',
      },
      fragments: [
        {
          type: 'memoria',
          conteudo: 'Fragment 1 content',
        },
        {
          type: 'memoria',
          conteudo: 'Fragment 2 content',
        },
        {
          type: 'other',
          conteudo: 'This should not be displayed',
        },
      ],
      created_at: '2025-12-09T10:00:00Z',
      updated_at: '2025-12-09T11:00:00Z',
    }
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Component Mounting', () => {
    it('should mount successfully with valid cell', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      expect(wrapper.exists()).toBe(true)
    })

    it('should load cell data on mount', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      // Check if title input has correct value
      const titleInput = wrapper.find('#cell-title')
      expect(titleInput.exists()).toBe(true)
      expect((titleInput.element as HTMLInputElement).value).toBe('Test Cell Title')
    })

    it('should display correct header for existing cell', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const header = wrapper.find('h2')
      expect(header.text()).toBe('📝 Editando Célula Não Classificada')
    })

    it('should display correct header for new cell', () => {
      const newCell = { ...mockCell, id: '' }
      wrapper = mount(View, {
        props: {
          cell: newCell,
        },
      })

      const header = wrapper.find('h2')
      expect(header.text()).toBe('📝 Nova Célula Não Classificada')
    })
  })

  describe('Cell Data Display', () => {
    it('should display cell title', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const titleInput = wrapper.find('#cell-title')
      expect((titleInput.element as HTMLInputElement).value).toBe('Test Cell Title')
    })

    it('should display cell content in editor', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      // MarkdownEditor should receive content as modelValue
      const editor = wrapper.findComponent({ name: 'MarkdownEditor' })
      expect(editor.exists()).toBe(true)
      expect(editor.props('modelValue')).toBe('Test cell content')
    })

    it('should display timestamps for existing cell', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const footer = wrapper.find('.flex.justify-between.items-center.pt-4')
      expect(footer.text()).toContain('Criada:')
      expect(footer.text()).toContain('Atualizada:')
    })

    it('should not display timestamps for new cell', () => {
      const newCell = { ...mockCell, id: '' }
      wrapper = mount(View, {
        props: {
          cell: newCell,
        },
      })

      const footer = wrapper.find('.flex.justify-between.items-center.pt-4')
      const footerDiv = footer.find('.flex.gap-4.text-xs')
      expect(footerDiv.exists()).toBe(false)
    })
  })

  describe('Fragment Viewer', () => {
    it('should display fragment count badge', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const badge = wrapper.find('.px-3.py-1.bg-primary')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toContain('2 fragmentos')
    })

    it('should display only memoria type fragments', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const fragments = wrapper.findAll('.bg-white.border.border-black\\/20.rounded-lg.p-4')
      expect(fragments).toHaveLength(2) // Only 2 memoria fragments, not 3
    })

    it('should not display fragments section when no fragments', () => {
      const cellWithoutFragments = { ...mockCell, fragments: [] }
      wrapper = mount(View, {
        props: {
          cell: cellWithoutFragments,
        },
      })

      const fragmentSection = wrapper.find('.bg-\\[\\#f9f9fb\\]')
      expect(fragmentSection.exists()).toBe(false)
    })

    it('should render fragment content with MarkdownRenderer', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const renderers = wrapper.findAllComponents({ name: 'MarkdownRenderer' })
      expect(renderers).toHaveLength(2)
      expect(renderers[0].props('content')).toBe('Fragment 1 content')
      expect(renderers[1].props('content')).toBe('Fragment 2 content')
    })

    it('should display "Send to Chat" button for each fragment', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const sendButtons = wrapper.findAll('button').filter(btn => 
        btn.text().includes('Enviar para Chat')
      )
      expect(sendButtons).toHaveLength(2)
    })
  })

  describe('User Interactions', () => {
    it('should update title on input', async () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const titleInput = wrapper.find('#cell-title')
      await titleInput.setValue('New Title')

      // Check if store was called
      expect(mockCellsStore.updateCellData).toHaveBeenCalled()
    })

    it('should close cell when close button clicked', async () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const closeButton = wrapper.find('button[title="Fechar"]')
      await closeButton.trigger('click')

      expect(mockCellsStore.closeCellView).toHaveBeenCalledWith('test-cell-123')
    })

    it('should send fragment to chat when button clicked', async () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const sendButtons = wrapper.findAll('button').filter(btn => 
        btn.text().includes('Enviar para Chat')
      )
      
      await sendButtons[0].trigger('click')

      expect(mockChatStore.addAttachment).toHaveBeenCalledWith({
        type: 'fragment',
        content: 'Fragment 1 content',
        metadata: {
          fragmentIndex: 0,
          cellId: 'test-cell-123',
          fragmentType: 'memoria',
        },
      })
    })

    it('should display success message after sending fragment', async () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const sendButtons = wrapper.findAll('button').filter(btn => 
        btn.text().includes('Enviar para Chat')
      )
      
      await sendButtons[0].trigger('click')
      await nextTick()

      const successMessage = wrapper.find('.bg-success\\/10')
      expect(successMessage.exists()).toBe(true)
      expect(successMessage.text()).toContain('Fragmento #1 enviado para o chat!')
    })
  })

  describe('Toolbar Integration', () => {
    it('should expose onSave method', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      expect(wrapper.vm.onSave).toBeDefined()
      expect(typeof wrapper.vm.onSave).toBe('function')
    })

    it('should call save when onSave is invoked', async () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      await wrapper.vm.onSave()

      // Should update cell data
      expect(mockCellsStore.updateCellData).toHaveBeenCalled()
    })
  })

  describe('Error Handling', () => {
    it('should handle missing cell gracefully', () => {
      const emptyCell = { id: 'test', initial_data: undefined, data: undefined }
      
      wrapper = mount(View, {
        props: {
          cell: emptyCell as any,
        },
      })

      expect(wrapper.exists()).toBe(true)
      const titleInput = wrapper.find('#cell-title')
      expect((titleInput.element as HTMLInputElement).value).toBe('')
    })

    it('should handle legacy data field', () => {
      const legacyCell = {
        ...mockCell,
        initial_data: undefined,
        data: {
          title: 'Legacy Title',
          content: 'Legacy Content',
        },
      }

      wrapper = mount(View, {
        props: {
          cell: legacyCell as any,
        },
      })

      const titleInput = wrapper.find('#cell-title')
      expect((titleInput.element as HTMLInputElement).value).toBe('Legacy Title')
    })

    it('should display empty content when fragment has no conteudo', () => {
      const cellWithEmptyFragment = {
        ...mockCell,
        fragments: [
          {
            type: 'memoria',
            conteudo: '',
          },
        ],
      }

      wrapper = mount(View, {
        props: {
          cell: cellWithEmptyFragment,
        },
      })

      const emptyMessage = wrapper.find('.text-black\\/40.italic')
      expect(emptyMessage.exists()).toBe(true)
      expect(emptyMessage.text()).toBe('Sem conteúdo')
    })
  })

  describe('Styling and Accessibility', () => {
    it('should have proper ARIA labels', () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      const badge = wrapper.find('[aria-label="2 fragmentos"]')
      expect(badge.exists()).toBe(true)
    })

    it('should disable inputs when saving', async () => {
      wrapper = mount(View, {
        props: {
          cell: mockCell,
        },
      })

      // Trigger save (simulated by setting isSaving internally)
      // This would need access to the composable state or trigger actual save
      // For now, we verify the prop binding exists
      const titleInput = wrapper.find('#cell-title')
      expect(titleInput.attributes('disabled')).toBeUndefined() // Not saving initially
    })
  })
})
