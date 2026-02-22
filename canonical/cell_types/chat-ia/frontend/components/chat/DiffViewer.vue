/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-14",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-14",
 *   "theme_compliance": 100,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <div class="diff-viewer bg-surface dark:bg-surface-dark rounded-lg border border-border dark:border-border-dark overflow-hidden">
    <!-- Header with stats -->
    <div class="diff-header bg-surface-hover dark:bg-surface-hover-dark px-4 py-2 border-b border-border dark:border-border-dark">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-text-primary dark:text-text-primary-dark">
          {{ t('diffViewer.title') }}
        </h3>
        <div class="flex gap-3 text-xs">
          <span class="text-success dark:text-success-dark">
            {{ t('diffViewer.additions', { count: stats.additions }) }}
          </span>
          <span class="text-danger dark:text-danger-dark">
            {{ t('diffViewer.deletions', { count: stats.deletions }) }}
          </span>
        </div>
      </div>
    </div>
    
    <!-- Diff content -->
    <div class="diff-content overflow-x-auto">
      <table class="w-full text-sm font-mono">
        <tbody>
          <tr
            v-for="(line, index) in displayedDiff"
            :key="index"
            :class="getLineClass(line.type)"
          >
            <td class="line-number px-2 py-0.5 text-right text-text-secondary dark:text-text-secondary-dark select-none border-r border-border dark:border-border-dark w-12">
              {{ line.lineNumber }}
            </td>
            <td class="line-content px-3 py-0.5 whitespace-pre">
              <span :class="getContentClass(line.type)">{{ line.content }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- Show more/less controls if diff is long -->
    <div v-if="diff.length > maxDisplayLines" class="diff-footer bg-surface-hover dark:bg-surface-hover-dark px-4 py-2 border-t border-border dark:border-border-dark">
      <button
        class="text-xs text-primary dark:text-primary-dark hover:underline"
        @click="toggleExpanded"
      >
        {{ expanded ? t('diffViewer.showLess') : t('diffViewer.showMore', { count: diff.length - maxDisplayLines }) }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getDiffStats } from '@/utils/diffUtils'

const { t } = useI18n()

const props = defineProps({
  /**
   * Diff array from diffUtils.computeDiff()
   */
  diff: {
    type: Array,
    required: true
  },
  
  /**
   * Maximum lines to display before requiring expansion
   */
  maxDisplayLines: {
    type: Number,
    default: 100
  }
})

const expanded = ref(false)

const stats = computed(() => getDiffStats(props.diff))

const displayedDiff = computed(() => {
  if (expanded.value || props.diff.length <= props.maxDisplayLines) {
    return props.diff
  }
  return props.diff.slice(0, props.maxDisplayLines)
})

function getLineClass(type) {
  const classes = {
    added: 'bg-success/10 dark:bg-success-dark/10',
    deleted: 'bg-danger/10 dark:bg-danger-dark/10',
    unchanged: ''
  }
  return classes[type] || ''
}

function getContentClass(type) {
  const classes = {
    added: 'text-success dark:text-success-dark',
    deleted: 'text-danger dark:text-danger-dark',
    unchanged: 'text-text-primary dark:text-text-primary-dark'
  }
  return classes[type] || ''
}

function toggleExpanded() {
  expanded.value = !expanded.value
}
</script>

<style scoped>
.diff-viewer {
  max-height: 600px;
}

.diff-content {
  max-height: 500px;
  overflow-y: auto;
}

.line-number {
  min-width: 3rem;
}

.line-content {
  width: 100%;
}
</style>
