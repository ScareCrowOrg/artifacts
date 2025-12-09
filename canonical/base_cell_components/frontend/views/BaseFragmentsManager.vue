<template>
  <div class="flex flex-col h-full p-6 gap-4 overflow-y-auto bg-white">
    <!-- Header -->
    <div class="flex justify-between items-center pb-4 border-b-2 border-black/20">
      <h2 class="m-0 text-2xl text-black font-semibold">
        📚 Gerenciador de Fragmentos
      </h2>
      <button
        class="w-6 h-6 text-lg border-0 bg-background hover:bg-background cursor-pointer rounded flex items-center justify-center transition-colors"
        title="Fechar"
        @click="handleClose"
      >
        ×
      </button>
    </div>

    <!-- Cell Info -->
    <div class="bg-[#f9f9fb] border border-black/10 rounded-lg p-4">
      <div class="flex items-center gap-3">
        <span class="text-sm font-medium text-black/60">Célula:</span>
        <code class="px-2 py-1 bg-white border border-black/10 rounded text-xs font-mono text-primary">
          {{ cellId }}
        </code>
      </div>
    </div>

    <!-- Add Fragment Section -->
    <div class="bg-[#f9f9fb] border border-black/10 rounded-lg p-4">
      <h3 class="m-0 mb-3 text-lg font-semibold text-black/90">
        ➕ Adicionar Novo Fragmento
      </h3>
      
      <div class="flex flex-col gap-3">
        <!-- Fragment Type -->
        <div class="flex flex-col gap-1">
          <label for="fragment-type" class="font-semibold text-sm text-black/60">
            Tipo do Fragmento
          </label>
          <select
            id="fragment-type"
            v-model="newFragmentType"
            class="px-3 py-2 border border-black/20 rounded-md text-base bg-white text-black focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          >
            <option value="memoria">📝 Memória</option>
            <option value="code">💻 Código</option>
            <option value="note">📄 Nota</option>
            <option value="reference">🔗 Referência</option>
          </select>
        </div>

        <!-- Fragment Content -->
        <div class="flex flex-col gap-1">
          <label for="fragment-content" class="font-semibold text-sm text-black/60">
            Conteúdo (Markdown)
          </label>
          <textarea
            id="fragment-content"
            v-model="newFragmentContent"
            class="px-3 py-2 border border-black/20 rounded-md text-base bg-white text-black focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent min-h-[150px] font-mono text-sm"
            placeholder="Digite o conteúdo do fragmento em Markdown..."
          />
        </div>

        <!-- Add Button -->
        <button
          class="btn btn-primary"
          :disabled="!canAddFragment || isAdding"
          @click="handleAddFragment"
        >
          {{ isAdding ? '⏳ Adicionando...' : '➕ Adicionar Fragmento' }}
        </button>
      </div>
    </div>

    <!-- Fragments List -->
    <div class="flex flex-col gap-3">
      <div class="flex justify-between items-center">
        <h3 class="m-0 text-lg font-semibold text-black/90">
          📋 Fragmentos Existentes
        </h3>
        <span
          class="px-3 py-1 bg-primary text-white rounded-full text-xs font-semibold"
          :aria-label="`${fragmentCount} fragmentos`"
        >
          {{ fragmentCount }}
          {{ fragmentCount === 1 ? 'fragmento' : 'fragmentos' }}
        </span>
      </div>

      <!-- Loading State -->
      <div
        v-if="isLoading"
        class="flex items-center justify-center py-12"
      >
        <div class="text-black/60">⏳ Carregando fragmentos...</div>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="fragmentCount === 0"
        class="bg-[#f9f9fb] border border-dashed border-black/20 rounded-lg p-8 text-center"
      >
        <div class="text-4xl mb-3">📭</div>
        <p class="text-black/60 m-0">
          Nenhum fragmento encontrado para esta célula.
        </p>
        <p class="text-sm text-black/40 mt-2 m-0">
          Use o formulário acima para adicionar fragmentos.
        </p>
      </div>

      <!-- Fragments -->
      <div
        v-else
        class="flex flex-col gap-4"
      >
        <div
          v-for="(fragment, index) in fragments"
          :key="`fragment-${index}`"
          class="bg-white border border-black/20 rounded-lg p-4 shadow-sm transition-shadow hover:shadow-md"
        >
          <!-- Fragment Header -->
          <div class="flex justify-between items-center mb-3 pb-2 border-b border-black/10">
            <div class="flex items-center gap-3">
              <span
                class="px-2 py-1 bg-primary/10 border border-primary/30 rounded text-xs font-medium text-primary"
              >
                {{ getFragmentTypeLabel(fragment.type) }}
              </span>
              <span class="text-sm text-black/60 font-medium">
                #{{ index + 1 }}
              </span>
            </div>
            <button
              class="px-3 py-2 border border-primary rounded-md bg-white text-primary text-xs font-medium cursor-pointer transition-all whitespace-nowrap hover:bg-primary hover:text-white hover:-translate-y-px hover:shadow-[0_2px_8px_rgba(98,0,234,0.3)]"
              :title="`Enviar fragmento #${index + 1} para o chat`"
              @click="handleSendToChat(fragment, index)"
            >
              💬 Enviar para Chat
            </button>
          </div>

          <!-- Fragment Content -->
          <div class="fragment-content text-black/90">
            <div v-if="fragment.conteudo" class="markdown-scroll">
              <MarkdownRenderer :content="fragment.conteudo" />
            </div>
            <div v-else class="text-black/40 italic text-center py-3">
              <em>Sem conteúdo</em>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error/Success Messages -->
    <div
      v-if="errorMessage"
      class="p-3 rounded-md text-sm bg-error/10 border border-error/20 text-error"
    >
      {{ errorMessage }}
    </div>
    <div
      v-if="successMessage"
      class="p-3 rounded-md text-sm bg-success/10 border border-success/20 text-success"
    >
      {{ successMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useNotebookStore } from '@/stores/useNotebookStore'
import { useBaseCellFeatures } from '../composables/useBaseCellFeatures'
import type { CellFragment } from '@/types/baseCell'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'

/**
 * Props interface for BaseFragmentsManager
 */
interface Props {
  /** ID of the cell whose fragments to manage */
  cellId: string
}

const props = defineProps<Props>()

console.group('[BaseFragmentsManager] 🎨 Component mounted')
console.log('📦 Cell ID:', props.cellId)
console.groupEnd()

// ============================================================
// Stores
// ============================================================
const notebookStore = useNotebookStore()

// ============================================================
// State
// ============================================================
const isLoading = ref(false)
const isAdding = ref(false)
const newFragmentType = ref('memoria')
const newFragmentContent = ref('')

// ============================================================
// Base Cell Features
// ============================================================
// We need to determine the cell type
// For now, we'll use a generic type, but this should be passed or inferred
const cellType = ref('unclassified-cell') // TODO: Get actual cell type

const baseCellApi = useBaseCellFeatures(
  computed(() => props.cellId),
  cellType
)

// Extract needed properties and methods
const { errorMessage, successMessage, sendFragmentToChat, addFragment } = baseCellApi

// ============================================================
// Computed
// ============================================================

/**
 * Get cell from notebook store
 */
const cell = computed(() => {
  return notebookStore.cells[props.cellId]
})

/**
 * Get fragments from cell
 */
const fragments = computed<CellFragment[]>(() => {
  if (!cell.value || !cell.value.fragments) {
    return []
  }
  return cell.value.fragments as CellFragment[]
})

/**
 * Get fragment count
 */
const fragmentCount = computed(() => {
  return fragments.value.length
})

/**
 * Check if can add fragment
 */
const canAddFragment = computed(() => {
  return newFragmentContent.value.trim().length > 0
})

// ============================================================
// Methods
// ============================================================

/**
 * Get fragment type label with emoji
 */
function getFragmentTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    'memoria': '📝 Memória',
    'code': '💻 Código',
    'note': '📄 Nota',
    'reference': '🔗 Referência',
  }
  return labels[type] || `📋 ${type}`
}

/**
 * Handle add fragment button click
 */
async function handleAddFragment(): Promise<void> {
  console.group('[BaseFragmentsManager] ➕ Adding fragment')
  console.log('📝 Type:', newFragmentType.value)
  console.log('📄 Content length:', newFragmentContent.value.length)

  if (!canAddFragment.value) {
    console.warn('⚠️ Cannot add empty fragment')
    console.groupEnd()
    return
  }

  isAdding.value = true

  try {
    const fragmentData: CellFragment = {
      type: newFragmentType.value,
      conteudo: newFragmentContent.value.trim(),
    }

    await addFragment(fragmentData)

    // Clear form on success
    newFragmentContent.value = ''
    newFragmentType.value = 'memoria'

    console.log('✅ Fragment added and form cleared')
  } catch (error: any) {
    console.error('❌ Error adding fragment:', error)
  } finally {
    isAdding.value = false
    console.groupEnd()
  }
}

/**
 * Handle send fragment to chat
 */
function handleSendToChat(fragment: CellFragment, index: number): void {
  console.log('[BaseFragmentsManager] 💬 Sending fragment to chat:', index)
  sendFragmentToChat(fragment, index)
}

/**
 * Handle close button click
 */
function handleClose(): void {
  console.log('[BaseFragmentsManager] ❌ Close button clicked')
  baseCellApi.closeCell()
}

// ============================================================
// Lifecycle
// ============================================================

onMounted(() => {
  console.group('[BaseFragmentsManager] 🔄 Component mounted lifecycle')
  console.log('📦 Cell ID:', props.cellId)
  console.log('🧩 Fragments:', fragmentCount.value)
  console.groupEnd()
})
</script>

<style scoped>
/* Fragment markdown content styling */
.fragment-content {
  max-height: 400px;
  overflow-y: auto;
}

.markdown-scroll {
  overflow-y: auto;
}

/* Custom scrollbar for fragments */
.fragment-content::-webkit-scrollbar {
  width: 6px;
}

.fragment-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.fragment-content::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 3px;
}

.fragment-content::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* Button styles */
.btn {
  @apply px-4 py-2 rounded-md font-medium cursor-pointer transition-all;
}

.btn-primary {
  @apply bg-primary text-white border-0;
}

.btn-primary:hover:not(:disabled) {
  @apply -translate-y-px shadow-lg;
}

.btn-primary:disabled {
  @apply opacity-50 cursor-not-allowed;
}
</style>
