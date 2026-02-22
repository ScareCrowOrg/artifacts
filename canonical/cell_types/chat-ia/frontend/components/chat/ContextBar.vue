/**
 * @metadata {
 *   "theme_validated": true,
 *   "i18n_validated": true,
 *   "component": "ContextBar",
 *   "purpose": "Display file attachments as chips for Agent Mode context",
 *   "mvp": "MVP 4.1 - Interface Mutante"
 * }
 */
<template>
  <transition name="context-bar-slide">
    <div
      v-if="hasFiles"
      class="context-bar border-t px-4 py-2"
      data-testid="context-bar"
    >
      <div class="flex items-center gap-2 mb-1">
        <span class="text-xs font-semibold text-opacity-70">
          📎 {{ $t('contextBar.filesInContext') }}:
        </span>
      </div>
      
      <div class="flex flex-wrap gap-2">
        <div
          v-for="attachment in attachments"
          :key="attachment.filename"
          class="file-chip flex items-center gap-2 px-3 py-1 rounded-full border text-sm transition-all duration-200"
          :data-testid="`context-chip-${attachment.filename}`"
        >
          <span class="file-icon">📄</span>
          <span class="file-name truncate max-w-[200px]">
            {{ attachment.filename }}
          </span>
          <button
            class="remove-btn p-0.5 rounded-full hover:bg-opacity-20 transition-colors duration-150"
            :title="$t('contextBar.removeFile')"
            @click="handleRemove(attachment.filename)"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'

const log = createLogger('chat:context-bar')
const { t: $t } = useI18n()

interface Attachment {
  filename: string
  content: string
  size: number
  type: string
  path?: string
}

interface Props {
  attachments: Attachment[]
  onRemove?: (filename: string) => void
}

const props = withDefaults(defineProps<Props>(), {
  attachments: () => [],
  onRemove: undefined,
})

const hasFiles = computed(() => props.attachments.length > 0)

function handleRemove(_filename: string): void {
  if (props.onRemove) {
    props.onRemove(_filename)
    log.debug('File removed from context', { filename: _filename })
  }
}
</script>

<style scoped>
.context-bar {
  background: color-mix(in srgb, var(--color-primary) 5%, var(--color-surface));
  border-color: var(--color-border);
}

.file-chip {
  background: var(--color-surface);
  border-color: color-mix(in srgb, var(--color-primary) 30%, var(--color-border));
  color: var(--color-text-primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.file-chip:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.file-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.file-name {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.875rem;
}

.remove-btn {
  color: var(--color-text-tertiary);
  font-size: 0.75rem;
  line-height: 1;
  flex-shrink: 0;
}

.remove-btn:hover {
  color: var(--color-error);
  background: color-mix(in srgb, var(--color-error) 10%, transparent);
}

.context-bar-slide-enter-active,
.context-bar-slide-leave-active {
  transition: all 0.3s ease;
}

.context-bar-slide-enter-from,
.context-bar-slide-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
  overflow: hidden;
}
</style>
