/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-11",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div
    class="border-t p-4 flex-shrink-0 sticky bottom-0 z-10"
    style="border-color: var(--color-border); background: var(--color-surface);"
    data-testid="chat-input-container"
  >
    <!-- Attachment Chips Section -->
    <div v-if="chat.attachments?.value?.length > 0" class="mb-3">
      <div class="flex items-center gap-2 mb-2">
        <span class="text-xs font-semibold" style="color: var(--color-text-secondary);">
          📎 {{ $t('chatInput.attachedFiles') }}:
        </span>
      </div>
      <div class="flex flex-nowrap gap-2 overflow-x-auto pb-1">
        <div
          v-for="attachment in chat.attachments.value"
          :key="attachment.filename"
          class="attachment-chip flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm transition-all duration-200"
          :data-testid="`attachment-chip-${attachment.filename}`"
        >
          <span class="text-base flex-shrink-0">📄</span>
          <span class="truncate max-w-[200px] font-mono text-xs">
            {{ attachment.filename }}
          </span>
          <button
            class="magnify-btn p-1 rounded-full hover:bg-opacity-20 transition-colors duration-150 flex-shrink-0"
            :title="$t('chatInput.openInEditor')"
            :aria-label="$t('chatInput.openInEditor')"
            @click="handleOpenFile(attachment)"
          >
            🔍
          </button>
          <button
            class="remove-btn p-1 rounded-full hover:bg-opacity-20 transition-colors duration-150 flex-shrink-0"
            :title="$t('chatInput.removeAttachment')"
            :aria-label="$t('chatInput.removeAttachment')"
            @click="handleRemoveAttachment(attachment.filename)"
          >
            ✕
          </button>
        </div>
      </div>
    </div>

    <!-- Textarea with character counter -->
    <div class="relative mb-2">
      <textarea
        :value="chat.userInput.value"
        :placeholder="$t('chatInput.placeholder')"
        rows="2"
        :disabled="chat.isLoading.value"
        :class="[
          'w-full px-3 py-2 pb-8 border rounded-md resize-y font-sans transition-colors duration-200',
          isAgentMode
            ? 'live-wire-glow'
            : '',
          promptWarning && !promptLimitReached
            ? 'border-warning focus:shadow-warning'
            : '',
          promptLimitReached
            ? 'border-error focus:shadow-error'
            : 'focus:border-primary focus:shadow-primary',
          'focus:outline-none',
        ]"
        style="background: var(--color-surface); color: var(--color-text-primary); border-color: var(--color-border);"
        data-testid="chat-input"
        @keydown.enter="handleEnter"
        @input="handleInput"
        @focus="onInputFocus"
      ></textarea>
      <div
        :class="[
          'absolute bottom-1 right-2 text-xs flex items-center gap-1 px-1.5 py-0.5 rounded',
          promptWarning && !promptLimitReached
            ? 'text-warning font-medium'
            : '',
          promptLimitReached ? 'text-error font-bold' : '',
        ]"
        style="background: var(--color-surface); color: var(--color-text-tertiary);"
      >
        {{ (chat.promptCharCount.value ?? 0).toLocaleString() }} /
        {{ (chat.promptMaxChars ?? 10000).toLocaleString() }}
        <span v-if="promptLimitReached" class="text-xs">{{ $t('chatInput.limitExceeded') }}</span>
        <span v-else-if="promptWarning" class="text-xs">{{ $t('chatInput.nearLimit') }}</span>
      </div>
    </div>

    <button
      :disabled="!chat.canSend.value"
      :class="[
        'px-3 py-1.5 text-sm rounded-md transition-all duration-200',
        chat.canSend.value
          ? 'bg-primary hover:bg-primary-hover text-white cursor-pointer'
          : 'cursor-not-allowed opacity-50',
      ]"
      :style="chat.canSend.value ? '' : 'background: var(--color-background); color: var(--color-text-tertiary);'"
      data-testid="chat-send-button"
      @click="chat.sendMessage()"
    >
      {{ chat.isLoading.value ? '⏳' : '📤' }} {{ $t('chatInput.sendButton') }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useCellManagement } from '../../composables/useCellManagement'

const props = defineProps({
  chat: {
    type: Object,
    required: true,
  },
  onInputFocus: {
    type: Function,
    default: () => {},
  },
  onEnter: {
    type: Function,
    default: () => {},
  },
  isAgentMode: {
    type: Boolean,
    default: false,
  },
})

const promptWarning = computed(() => props.chat.promptWarning.value)
const promptLimitReached = computed(() => props.chat.promptLimitReached.value)

// Get cell management composable for opening files
const cellMgmt = useCellManagement()

function handleInput(event) {
  // TODO: Refactor to emit event instead of mutating prop
  // eslint-disable-next-line vue/no-mutating-props
  props.chat.userInput.value = event.target.value
}

function handleEnter(event) {
  if (props.onEnter) {
    props.onEnter(event)
  }
}

/**
 * Open file in file-editor-v2 cell
 */
function handleOpenFile(attachment) {
  const fileInfo = {
    fileName: attachment.filename,
    filePath: attachment.path || '.',  // Use current directory as default if path is undefined
  }
  cellMgmt.createFileEditorCell(fileInfo)
}

/**
 * Remove attachment from chat
 */
function handleRemoveAttachment(filename) {
  if (props.chat.removeAttachment) {
    props.chat.removeAttachment(filename)
  }
}
</script>

.focus\:shadow-primary:focus {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 10%, transparent);
}

.focus\:shadow-warning:focus {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-warning) 10%, transparent);
}

.focus\:shadow-error:focus {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-error) 10%, transparent);
}

<style scoped>
/* Attachment chips styling */
.attachment-chip {
  background: var(--color-surface);
  border-color: color-mix(in srgb, var(--color-primary) 30%, var(--color-border));
  color: var(--color-text-primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.attachment-chip:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.magnify-btn {
  color: var(--color-primary);
  font-size: 1rem;
  line-height: 1;
}

.magnify-btn:hover {
  background: color-mix(in srgb, var(--color-primary) 15%, transparent);
}

.remove-btn {
  color: var(--color-text-tertiary);
  font-size: 0.875rem;
  line-height: 1;
}

.remove-btn:hover {
  color: var(--color-error);
  background: color-mix(in srgb, var(--color-error) 10%, transparent);
}

/* Live-Wire Glow Effect (MVP 4.1 - Amber Glow for Agent Mode) */
.live-wire-glow {
  border-color: rgb(251, 191, 36) !important;
  box-shadow: 
    0 0 8px rgba(251, 191, 36, 0.4),
    0 0 16px rgba(251, 191, 36, 0.2),
    inset 0 0 8px rgba(251, 191, 36, 0.1);
  animation: live-wire-pulse 2s ease-in-out infinite;
}

.live-wire-glow:focus {
  box-shadow: 
    0 0 12px rgba(251, 191, 36, 0.6),
    0 0 24px rgba(251, 191, 36, 0.3),
    inset 0 0 12px rgba(251, 191, 36, 0.15);
}

@keyframes live-wire-pulse {
  0%, 100% {
    box-shadow: 
      0 0 8px rgba(251, 191, 36, 0.4),
      0 0 16px rgba(251, 191, 36, 0.2),
      inset 0 0 8px rgba(251, 191, 36, 0.1);
  }
  50% {
    box-shadow: 
      0 0 12px rgba(251, 191, 36, 0.6),
      0 0 24px rgba(251, 191, 36, 0.3),
      inset 0 0 12px rgba(251, 191, 36, 0.15);
  }
}
</style>

