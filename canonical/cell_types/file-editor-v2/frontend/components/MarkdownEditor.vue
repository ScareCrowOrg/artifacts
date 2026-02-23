/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-11",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-11",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <div
    class="flex flex-col h-full border border-border dark:border-border-dark rounded-lg overflow-hidden w-full"
  >
    <!-- Editor Toolbar -->
    <div
      class="flex items-center gap-1 px-2 py-1 bg-surface dark:bg-surface-dark border-b border-border dark:border-border-dark"
    >
      <button
        type="button"
        class="px-3 py-1.5 text-sm font-medium text-text-secondary dark:text-text-secondary-dark hover:text-primary hover:bg-surface dark:hover:bg-surface-dark rounded transition-colors"
        :title="isPreviewMode ? $t('markdownEditor.edit') : $t('markdownEditor.viewPreviewTitle')"
        :aria-label="
          isPreviewMode
            ? $t('markdownEditor.switchToEditMode')
            : $t('markdownEditor.switchToPreviewMode')
        "
        @click="toggleMode"
      >
        {{ isPreviewMode ? $t('markdownEditor.editButton') : $t('markdownEditor.previewButton') }}
      </button>
    </div>

    <!-- Edit Mode -->
    <textarea
      v-if="!isPreviewMode"
      ref="textarea"
      v-model="localContent"
      class="flex-1 w-full min-w-0 min-h-[300px] max-h-[600px] box-border p-4 border-none resize-y font-mono text-sm leading-relaxed bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none placeholder:text-text-secondary dark:placeholder:text-text-secondary-dark"
      :placeholder="computedPlaceholder"
      :readonly="readonly"
      :aria-label="ariaLabel || $t('markdownEditor.editorAriaLabel')"
      @input="onInput"
      @blur="onBlur"
    ></textarea>

    <!-- Preview Mode -->
    <div
      v-else
      class="flex-1 p-4 overflow-y-auto bg-surface dark:bg-surface-dark"
      :aria-label="$t('markdownEditor.previewAriaLabel')"
    >
      <MarkdownRenderer :content="localContent" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownRenderer from './MarkdownRenderer.vue'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: '',
  },
  readonly: {
    type: Boolean,
    default: false,
  },
  ariaLabel: {
    type: String,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue'])

const localContent = ref(props.modelValue)
const isPreviewMode = ref(false)

const computedPlaceholder = computed(() => {
  return props.placeholder || t('markdownEditor.placeholder')
})

watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue !== localContent.value) {
      localContent.value = newValue
    }
  }
)

function toggleMode() {
  isPreviewMode.value = !isPreviewMode.value
}

function onInput() {
  emit('update:modelValue', localContent.value)
}

function onBlur() {
  emit('update:modelValue', localContent.value)
}
</script>
