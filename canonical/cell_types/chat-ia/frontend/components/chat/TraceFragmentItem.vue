/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_keys_used": [
 *     "chat.traceFragment.userMessage",
 *     "chat.traceFragment.originalQuery",
 *     "chat.traceFragment.expandedQuery",
 *     "chat.traceFragment.ragChunks",
 *     "chat.traceFragment.score",
 *     "chat.traceFragment.llmResponse",
 *     "chat.traceFragment.fullData",
 *     "chat.traceFragment.notAvailable"
 *   ],
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "dark_mode_support": "full",
 *   "theme_issues_found": 0
 * }
 */
<template>
  <div class="border border-border dark:border-gray-700 rounded-lg mb-2 overflow-hidden">
    <!-- Fragment header - always visible -->
    <div
      :class="[
        'flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors',
        isExpanded ? 'bg-surface-hover dark:bg-gray-800' : 'bg-surface dark:bg-gray-900 hover:bg-surface-hover dark:hover:bg-gray-800',
      ]"
      @click="toggleExpanded"
    >
      <!-- Expand/collapse icon -->
      <button
        class="p-0 min-w-[20px] w-5 h-5 border-none bg-transparent hover:bg-surface-hover dark:hover:bg-gray-700 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
        @click.stop="toggleExpanded"
      >
        <span class="text-xs block text-text-primary dark:text-text-primary">{{ isExpanded ? '▼' : '▶' }}</span>
      </button>

      <!-- Stage icon -->
      <span class="text-2xl flex-shrink-0" :title="fragment.stageLabel">{{
        fragment.stageIcon
      }}</span>

      <!-- Stage info -->
      <div class="flex-grow min-w-0">
        <div class="flex items-center gap-2">
          <span
            :class="[
              'font-semibold text-sm',
              getStageColorClass(fragment.stage),
            ]"
            >{{ fragment.stageLabel }}</span
          >
          <span class="text-xs text-text-secondary dark:text-text-secondary">
            {{ formatTimestamp(fragment.timestamp) }}
          </span>
        </div>
      </div>
    </div>

    <!-- Fragment details - expandable -->
    <div v-if="isExpanded" class="px-4 py-3 bg-background dark:bg-gray-800 border-t border-border dark:border-gray-700">
      <!-- Fragment data -->
      <div class="space-y-3">
        <!-- User message (if available in data) -->
        <div
          v-if="fragment.data.user_message"
          class="bg-surface dark:bg-gray-900 p-3 rounded border border-border dark:border-gray-700"
        >
          <p class="text-xs text-text-secondary dark:text-text-secondary mb-1 font-semibold">{{ $t('chat.traceFragment.userMessage') }}</p>
          <p class="text-sm text-text-primary dark:text-text-primary">{{ fragment.data.user_message }}</p>
        </div>

        <!-- Original query (if available) -->
        <div
          v-if="fragment.data.query_original || fragment.data.original_query"
          class="bg-surface dark:bg-gray-900 p-3 rounded border border-border dark:border-gray-700"
        >
          <p class="text-xs text-text-secondary dark:text-text-secondary mb-1 font-semibold">{{ $t('chat.traceFragment.originalQuery') }}</p>
          <p class="text-sm text-text-primary dark:text-text-primary">
            {{ fragment.data.query_original || fragment.data.original_query }}
          </p>
        </div>

        <!-- Expanded query (if available) -->
        <div
          v-if="fragment.data.query_expanded || fragment.data.expanded_query"
          class="bg-surface dark:bg-gray-900 p-3 rounded border border-success-light dark:border-success-dark"
        >
          <p class="text-xs text-text-secondary dark:text-text-secondary mb-1 font-semibold">{{ $t('chat.traceFragment.expandedQuery') }}</p>
          <p class="text-sm text-text-primary dark:text-text-primary">
            {{ fragment.data.query_expanded || fragment.data.expanded_query }}
          </p>
        </div>

        <!-- RAG chunks (if available) -->
        <div
          v-if="fragment.data.chunks_retrieved || fragment.data.chunks"
          class="bg-surface dark:bg-gray-900 p-3 rounded border border-info-light dark:border-info"
        >
          <p class="text-xs text-text-secondary dark:text-text-secondary mb-1 font-semibold">
            {{ $t('chat.traceFragment.ragChunks', { count: getChunksCount(fragment.data) }) }}
          </p>
          <div v-if="fragment.data.chunks" class="mt-2 space-y-2 max-h-60 overflow-y-auto">
            <div
              v-for="(chunk, idx) in getChunks(fragment.data)"
              :key="idx"
              class="p-2 bg-info-light/10 dark:bg-info/20 rounded text-xs border border-info-light dark:border-info"
            >
              <p class="font-mono text-xs break-words text-text-primary dark:text-text-primary">
                {{ truncateText(chunk.content || chunk, 200) }}
              </p>
              <p v-if="chunk.metadata" class="text-text-secondary dark:text-text-secondary mt-1">
                {{ $t('chat.traceFragment.score', { score: chunk.metadata.score || $t('chat.traceFragment.notAvailable') }) }}
              </p>
            </div>
          </div>
        </div>

        <!-- LLM response (if available) -->
        <div
          v-if="fragment.data.response_text"
          class="bg-surface dark:bg-gray-900 p-3 rounded border border-primary-light dark:border-primary"
        >
          <p class="text-xs text-text-secondary dark:text-text-secondary mb-1 font-semibold">{{ $t('chat.traceFragment.llmResponse') }}</p>
          <p class="text-sm whitespace-pre-wrap text-text-primary dark:text-text-primary">
            {{ truncateText(fragment.data.response_text, 500) }}
          </p>
        </div>

        <!-- Generic data display (for other fields) -->
        <div class="bg-surface dark:bg-gray-900 p-3 rounded border border-border dark:border-gray-700">
          <p class="text-xs text-text-secondary dark:text-text-secondary mb-2 font-semibold">{{ $t('chat.traceFragment.fullData') }}</p>
          <pre
            class="text-xs overflow-x-auto bg-background dark:bg-gray-800 p-2 rounded border border-border dark:border-gray-700 max-h-40 overflow-y-auto text-text-primary dark:text-text-primary"
            >{{ JSON.stringify(fragment.data, null, 2) }}</pre
          >
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * TraceFragmentItem Component
 * Expandable display of a single trace fragment
 * 
 * Features:
 * - Expandable/collapsible view
 * - Stage-specific icons and colors
 * - Formatted display of common fields (queries, chunks, responses)
 * - Raw JSON view for full data
 * - Responsive layout with max heights for scrolling
 * 
 * Technical naming: All functions and variables in English
 */
import { ref } from 'vue'
import { getStageColor } from '@/services/tracesService.js'

/**
 * Props
 */
const props = defineProps({
  /**
   * Fragment data (formatted)
   * Should include: timestamp, stage, stageLabel, stageIcon, data
   */
  fragment: {
    type: Object,
    required: true,
  },
  /**
   * Initial expanded state
   */
  initiallyExpanded: {
    type: Boolean,
    default: false,
  },
})

/**
 * State
 */
const isExpanded = ref(props.initiallyExpanded)

/**
 * Toggle expanded state
 */
const toggleExpanded = () => {
  isExpanded.value = !isExpanded.value
}

/**
 * Format timestamp for display
 * @param {string} timestamp - ISO 8601 timestamp
 * @returns {string} Formatted time
 */
const formatTimestamp = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/**
 * Get Tailwind color class for stage
 * @param {string} stage - Stage identifier
 * @returns {string} Tailwind color class
 */
const getStageColorClass = (stage) => {
  return getStageColor(stage)
}

/**
 * Get chunks count from fragment data
 * @param {Object} data - Fragment data
 * @returns {number} Number of chunks
 */
const getChunksCount = (data) => {
  return data.chunks_retrieved || (data.chunks ? data.chunks.length : 0)
}

/**
 * Get chunks array from fragment data
 * @param {Object} data - Fragment data
 * @returns {Array} Chunks array
 */
const getChunks = (data) => {
  return data.chunks || []
}

/**
 * Truncate text to max length
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text
 */
const truncateText = (text, maxLength) => {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
</script>
