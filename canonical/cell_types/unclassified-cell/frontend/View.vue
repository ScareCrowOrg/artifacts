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

    <!-- Toolbar Actions -->
    <div class="flex gap-2 mb-2">
      <button
        class="btn btn-primary"
        :disabled="isSaving"
        @click="handleSave"
      >
        {{ isSaving ? '⏳ Salvando...' : '💾 Salvar Célula' }}
      </button>
      <button
        class="btn btn-secondary"
        @click="handleShowFragmentsManager"
      >
        📚 Gerenciar Fragmentos
      </button>
      <button
        class="btn btn-secondary"
        @click="handleAddFragment"
      >
        ➕ Adicionar Fragmento
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

    <!-- Fragment Summary (Compact) -->
    <div
      v-if="fragmentCount > 0"
      class="bg-[#f9f9fb] border border-black/10 rounded-lg p-3"
    >
      <div class="flex justify-between items-center">
        <span class="text-sm text-black/60">
          📚 Esta célula possui
          <strong class="text-primary">{{ fragmentCount }}</strong>
          {{ fragmentCount === 1 ? 'fragmento' : 'fragmentos' }}
        </span>
        <button
          class="px-3 py-1 border border-primary rounded-md bg-white text-primary text-xs font-medium cursor-pointer transition-all hover:bg-primary hover:text-white"
          @click="handleShowFragmentsManager"
        >
          Ver Fragmentos
        </button>
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
import { ref, computed } from 'vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import { useUnclassifiedCell, type UnclassifiedCell } from './composables/useUnclassifiedCell'
import { useBaseCellFeatures } from '#artifacts/canonical/base_cell_components/frontend/composables/useBaseCellFeatures.ts'

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

// Use unclassified cell composable for cell-specific logic
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

// Use base cell features for common cell operations
// ARCHITECTURE PRINCIPLE: Pass cell instance to avoid store lookup
const baseCellApi = useBaseCellFeatures(
  computed(() => props.cell?.id || ''),
  computed(() => 'unclassified-cell'),
  {}, // options
  ref(props.cell) // Pass cell instance directly
)

/**
 * Handle close button click
 */
function onClose(): void {
  console.log('[UnclassifiedCellView] ❌ Close button clicked')
  closeCell()
}

/**
 * Handle save button click
 */
async function handleSave(): Promise<void> {
  console.log('[UnclassifiedCellView] 💾 Save button clicked')
  await saveCell()
}

/**
 * Handle save action (exposed for CellToolbar)
 */
async function onSave(): Promise<void> {
  console.log('[UnclassifiedCellView] 💾 Save triggered from toolbar')
  await saveCell()
}

/**
 * Handle show fragments manager button click
 */
function handleShowFragmentsManager(): void {
  console.log('[UnclassifiedCellView] 📚 Show fragments manager clicked')
  baseCellApi.showCellFragmentsManager()
}

/**
 * Handle add fragment button click
 */
function handleAddFragment(): void {
  console.log('[UnclassifiedCellView] ➕ Add fragment clicked')
  // For now, just open the fragments manager
  // In the future, this could open a dedicated "add fragment" modal
  baseCellApi.showCellFragmentsManager()
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

/* Button styles */
.btn {
  @apply px-4 py-2 rounded-md font-medium cursor-pointer transition-all border-0;
}

.btn-primary {
  @apply bg-primary text-white;
}

.btn-primary:hover:not(:disabled) {
  @apply -translate-y-px shadow-lg;
}

.btn-primary:disabled {
  @apply opacity-50 cursor-not-allowed;
}

.btn-secondary {
  @apply bg-white text-primary border border-primary;
}

.btn-secondary:hover {
  @apply bg-primary text-white -translate-y-px shadow-md;
}
</style>
