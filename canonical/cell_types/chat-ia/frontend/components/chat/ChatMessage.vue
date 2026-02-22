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
 *   "i18n_issues": 0
 * }
 */
<template>
  <div
    :class="[
      'mb-4 p-3 rounded-lg border',
      message.role === 'user'
        ? 'ml-12 message-user'
        : 'mr-12 message-assistant',
    ]"
  >
    <div class="flex items-center gap-2 mb-2 text-sm message-header">
      <span class="text-lg">{{ message.role === 'user' ? '👤' : '🤖' }}</span>
      <span class="font-semibold">{{
        message.role === 'user' ? $t('chatMessage.userLabel') : $t('chatMessage.aiLabel')
      }}</span>
      <span
        v-if="message.model"
        class="px-2 py-0.5 border rounded text-xs font-medium model-badge"
      >
        {{ getModelLabel(message.model) }}
      </span>
      <span class="ml-auto text-xs">{{ formatTime(message.timestamp) }}</span>
    </div>
    <div class="leading-relaxed">
      <MarkdownRenderer
        v-if="message.role === 'assistant'"
        :content="message.content"
        :aria-label="$t('chatMessage.aiResponseAriaLabel', { model: getModelLabel(message.model || $t('chatMessage.aiLabel')) })"
      />
      <div v-else class="whitespace-pre-wrap break-words">
        {{ message.content }}
      </div>
    </div>
    <div
      v-if="message.celula"
      class="mt-2 px-2 py-1 border rounded text-sm celula-badge"
    >
      {{ $t('chatMessage.cellCreatedBadge') }} <code>{{ message.celula.id }}</code>
    </div>
    <div v-if="message.role === 'assistant'" class="mt-2 flex gap-2 flex-wrap">
      <button
        class="px-3 py-1 border rounded text-xs transition-all duration-200 cursor-pointer btn-copy"
        :title="$t('chatMessage.copyTooltip')"
        @click="copyToClipboard"
      >
        {{ $t('chatMessage.copyButton') }}
      </button>
      <button
        class="px-3 py-1 border rounded text-xs transition-all duration-200 cursor-pointer btn-notebook"
        :title="$t('chatMessage.notebookTooltip')"
        @click="copyToNotebook"
      >
        {{ $t('chatMessage.notebookButton') }}
      </button>
      <TraceTimelineButton
        :conversation-id="message.conversation_id"
        @click="handleTimelineClick"
      />
    </div>
  </div>
</template>

<script setup>
import MarkdownRenderer from '../MarkdownRenderer.vue'
import TraceTimelineButton from './TraceTimelineButton.vue'
import { useGlobalEventsStore } from '@/stores/globalEvents'
import { useI18n } from 'vue-i18n'

const { t: $t } = useI18n()

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
  availableModels: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['show-timeline'])

const globalEvents = useGlobalEventsStore()

function formatTime(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getModelLabel(modelId) {
  const model = props.availableModels.find((m) => m.value === modelId)
  return model ? model.name : modelId
}

async function copyToClipboard() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    // Feedback opcional
  } catch (error) {
    console.error($t('chatMessage.copyError'), error)
  }
}

function copyToNotebook() {
  globalEvents.setCopiedContent(props.message.content)
}

function handleTimelineClick(conversationId) {
  emit('show-timeline', conversationId)
}
</script>

<style scoped>
.message-user {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  border-color: color-mix(in srgb, var(--color-primary) 20%, transparent);
}

.message-assistant {
  background: var(--color-surface);
  border-color: var(--color-border);
}

.message-header {
  color: var(--color-text-secondary);
}

.model-badge {
  background: color-mix(in srgb, var(--color-primary) 20%, transparent);
  border-color: color-mix(in srgb, var(--color-primary) 20%, transparent);
  color: var(--color-primary);
}

.celula-badge {
  background: color-mix(in srgb, var(--color-success) 10%, transparent);
  border-color: color-mix(in srgb, var(--color-success) 20%, transparent);
  color: var(--color-success);
}

.btn-copy {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  border-color: color-mix(in srgb, var(--color-primary) 20%, transparent);
}

.btn-copy:hover {
  background: color-mix(in srgb, var(--color-primary) 20%, transparent);
  border-color: var(--color-primary);
}

.btn-notebook {
  background: color-mix(in srgb, var(--color-success) 10%, transparent);
  border-color: color-mix(in srgb, var(--color-success) 20%, transparent);
}

.btn-notebook:hover {
  background: color-mix(in srgb, var(--color-success) 20%, transparent);
  border-color: var(--color-success);
}
</style>
