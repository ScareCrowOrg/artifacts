/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-16",
 *   "theme_compliance": 98,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-17",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="example-cell bg-surface dark:bg-gray-800 border border-border dark:border-gray-700 rounded-lg p-4 shadow-sm">
    <div class="cell-header mb-3">
      <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
        {{ cell.initial_data?.message || $t('exampleCell.defaultTitle') }}
      </h3>
    </div>

    <div class="cell-content space-y-4">
      <!-- Counter Display -->
      <div class="counter-section">
        <label class="block text-sm font-medium text-text-secondary dark:text-gray-400 mb-1">
          {{ $t('exampleCell.counter') }}
        </label>
        <div class="flex items-center gap-2">
          <span class="text-2xl font-bold text-primary dark:text-primary-light">
            {{ counter }}
          </span>
          <button
            class="px-3 py-1 bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover dark:hover:bg-primary-light transition"
            @click="incrementCounter"
          >
            {{ $t('exampleCell.increment') }}
          </button>
        </div>
      </div>

      <!-- Message Editor -->
      <div class="message-section">
        <label class="block text-sm font-medium text-text-secondary dark:text-gray-400 mb-1">
          {{ $t('exampleCell.message') }}
        </label>
        <input
          v-model="message"
          type="text"
          class="w-full px-3 py-2 border border-border dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 rounded focus:outline-none focus:ring-2 focus:ring-primary"
          @change="updateCell"
        />
      </div>

      <!-- Cell Info -->
      <div class="info-section text-xs text-text-secondary dark:text-gray-400">
        <p>{{ $t('exampleCell.cellId') }} {{ cell.id }}</p>
        <p>{{ $t('exampleCell.type') }} {{ cell.notebook_item_type_id }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t: $t } = useI18n()

const props = defineProps({
  cell: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:cell', 'execute'])

// Local reactive state
const message = ref(props.cell.initial_data?.message || 'Hello from Example Cell')
const counter = ref(props.cell.initial_data?.counter || 0)

// Watch for external cell changes
watch(() => props.cell.initial_data, (newData) => {
  if (newData) {
    message.value = newData.message || message.value
    counter.value = newData.counter || counter.value
  }
}, { deep: true })

// Increment counter
function incrementCounter() {
  counter.value++
  updateCell()
}

// Update cell data
function updateCell() {
  const updatedCell = {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      message: message.value,
      counter: counter.value
    }
  }
  emit('update:cell', updatedCell)
}
</script>

<style scoped>
.example-cell {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
