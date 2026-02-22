/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "dark_mode_support": "full",
 *   "theme_issues_found": 0
 * }
 */
<template>
  <button
    :disabled="!conversationId || disabled"
    :title="
      conversationId
        ? $t('chat.traceTimeline.viewTimelineTitle')
        : $t('chat.traceTimeline.noTraceTitle')
    "
    class="px-3 py-1 bg-primary-light/10 dark:bg-primary/20 border border-primary-light dark:border-primary rounded text-xs hover:bg-primary-light/20 dark:hover:bg-primary/30 hover:border-primary dark:hover:border-primary-hover transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-primary-light/10 dark:disabled:hover:bg-primary/20 text-text-primary dark:text-text-primary"
    @click="handleClick"
  >
    {{ $t('chat.traceTimeline.buttonLabel') }}
  </button>
</template>

<script setup>
/**
 * TraceTimelineButton Component
 * Button to trigger display of conversation trace timeline
 * 
 * Features:
 * - Disabled state when no conversationId available
 * - Hover effects with Tailwind CSS
 * - Accessibility support with title attribute
 * - Emits click event to parent
 * 
 * Technical naming: All functions and variables in English
 */

/**
 * Props
 */
const props = defineProps({
  /**
   * Conversation ID for trace lookup
   * If null/undefined, button is disabled
   */
  conversationId: {
    type: String,
    default: null,
  },
  /**
   * Additional disabled state (external control)
   */
  disabled: {
    type: Boolean,
    default: false,
  },
})

/**
 * Emits
 */
const emit = defineEmits(['click'])

/**
 * Handle button click
 * Emits click event with conversationId to parent
 */
const handleClick = () => {
  if (props.conversationId && !props.disabled) {
    emit('click', props.conversationId)
  }
}
</script>
