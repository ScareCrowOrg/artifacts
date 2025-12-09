<template>
  <div class="flex flex-col h-full p-6 gap-4 overflow-y-auto">
    <!-- Header with Toolbar Integration -->
    <div class="flex justify-between items-center pb-4 border-b-2 border-black/20">
      <h2 class="m-0 text-2xl text-black font-semibold">
        {{
          isNewCell
            ? '📝 Nova Célula Não Classificada'
            : '📝 Editando Célula Não Classificada'
        }}
      </h2>
      <button
        class="w-6 h-6 text-lg border-0 bg-background hover:bg-background cursor-pointer rounded flex items-center justify-center transition-colors"
        title="Fechar"
        @click="onClose"
      >
        ×
      </button>
    </div>

    <!-- Title Input -->
    <div class="flex flex-col gap-1">
      <label for="cell-title" class="font-semibold text-sm text-black/60"
        >Título da Célula</label
      >
      <input
        id="cell-title"
        v-model="cellData.title"
        type="text"
        class="px-3 py-2 border border-black/20 rounded-md text-base bg-white text-black focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
        placeholder="Digite o título da célula"
        :disabled="isSaving"
      />
    </div>

    <!-- Content Editor -->
    <div class="flex flex-col gap-1 flex-1 min-h-[300px]">
      <label class="font-semibold text-sm text-black/60">Conteúdo</label>
      <MarkdownEditor
        v-model="cellData.content"
        placeholder="Digite o conteúdo da célula em Markdown..."
        :readonly="isSaving"
      />
    </div>

    <!-- Fragment Viewer Section (Integrated) -->
    <div
      v-if="fragmentCount > 0"
      class="bg-[#f9f9fb] border-t-2 border-black/20 p-4 rounded-lg"
    >
      <div class="flex justify-between items-center mb-4 pb-3 border-b border-black/20">
        <h3 class="m-0 text-lg font-semibold text-black/90">
          📚 Fragmentos de Memória
        </h3>
        <span
          class="px-3 py-1 bg-primary text-white rounded-full text-xs font-semibold"
          :aria-label="`${fragmentCount} fragmentos`"
        >
          {{ fragmentCount }}
          {{ fragmentCount === 1 ? 'fragmento' : 'fragmentos' }}
        </span>
      </div>

      <div class="flex flex-col gap-4">
        <div
          v-for="(fragment, index) in memoryFragments"
          :key="`fragment-${index}`"
          class="bg-white border border-black/20 rounded-lg p-4 shadow-sm transition-shadow hover:shadow-md"
        >
          <div class="flex justify-between items-center mb-3 pb-2 border-b border-black/10">
            <div class="flex items-center gap-3">
              <span
                class="px-2 py-1 bg-primary/10 border border-primary/30 rounded text-xs font-medium text-primary"
              >
                📝 Memória
              </span>
              <span class="text-sm text-black/60 font-medium">#{{ index + 1 }}</span>
            </div>
            <button
              class="px-3 py-2 border border-primary rounded-md bg-white text-primary text-xs font-medium cursor-pointer transition-all whitespace-nowrap hover:bg-primary hover:text-white hover:-translate-y-px hover:shadow-[0_2px_8px_rgba(98,0,234,0.3)]"
              :title="`Enviar fragmento #${index + 1} como anexo para o chat`"
              @click="handleSendFragmentToChat(fragment, index)"
            >
              💬 Enviar para Chat
            </button>
          </div>

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

    <!-- Footer Actions -->
    <div class="flex justify-between items-center pt-4 border-t border-black/20">
      <div v-if="!isNewCell && cell" class="flex gap-4 text-xs text-black/60">
        <span class="whitespace-nowrap"
          >Criada: {{ formatDate(cell.created_at) }}</span
        >
        <span class="whitespace-nowrap"
          >Atualizada: {{ formatDate(cell.updated_at) }}</span
        >
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
import { ref } from 'vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import { useUnclassifiedCell, type UnclassifiedCell } from './composables/useUnclassifiedCell'

/**
 * Props interface for Unclassified Cell View
 */
interface Props {
  /** The unclassified cell instance */
  cell: UnclassifiedCell
}

const props = defineProps<Props>()

console.group('[UnclassifiedCellView] 🎨 Component mounted')
console.log('📦 Cell ID:', props.cell?.id || 'NEW')
console.log('📊 Initial data:', props.cell?.initial_data || props.cell?.data)
console.log('🧩 Fragments:', props.cell?.fragments?.length || 0)
console.groupEnd()

// Use unclassified cell composable
const {
  cellData,
  isLoading,
  isSaving,
  errorMessage,
  successMessage,
  isNewCell,
  memoryFragments,
  fragmentCount,
  saveCell,
  closeCell,
  sendFragmentToChat,
  formatDate,
} = useUnclassifiedCell(ref(props.cell))

/**
 * Handle close button click
 */
function onClose(): void {
  console.log('[UnclassifiedCellView] ❌ Close button clicked')
  closeCell()
}

/**
 * Handle save action (exposed for CellToolbar)
 */
async function onSave(): Promise<void> {
  console.log('[UnclassifiedCellView] 💾 Save triggered from toolbar')
  await saveCell()
}

/**
 * Handle send fragment to chat
 */
function handleSendFragmentToChat(fragment: any, index: number): void {
  console.log('[UnclassifiedCellView] 💬 Send fragment button clicked', index)
  sendFragmentToChat(fragment, index)
}

// Expose methods for parent component (CellToolbar) to call
defineExpose({
  onSave,
})
</script>

<style scoped>
/* Fragment markdown content styling */
.fragment-content {
  max-height: 300px;
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
</style>
