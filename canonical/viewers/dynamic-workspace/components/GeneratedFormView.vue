/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-05",
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-03-05",
 *   "source": "NEW — fallback form renderer when cell has no custom View.vue"
 * }
 */
<template>
  <div class="generated-form-view p-4 flex flex-col gap-4 h-full overflow-auto">
    <!-- Header -->
    <div class="form-header">
      <h3 class="text-base font-semibold text-gray-800 dark:text-white">
        {{ $t('generatedForm.title') }}
      </h3>
      <p v-if="cellTypeName" class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
        {{ cellTypeName }}
      </p>
    </div>

    <!-- No inputs message -->
    <p
      v-if="formFields.length === 0"
      class="text-sm text-gray-400 dark:text-gray-500 italic"
    >
      {{ $t('generatedForm.noInputs') }}
    </p>

    <!-- Form fields -->
    <div v-else class="form-fields flex flex-col gap-3">
      <div
        v-for="field in formFields"
        :key="field.name"
        class="form-field"
      >
        <label
          :for="`field-${field.name}`"
          class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
        >
          {{ field.label }}
          <span v-if="field.required" class="text-red-500 ml-1">*</span>
        </label>

        <!-- Enum → select -->
        <select
          v-if="field.type === 'enum'"
          :id="`field-${field.name}`"
          v-model="formData[field.name]"
          class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
        </select>

        <!-- Boolean → checkbox -->
        <input
          v-else-if="field.type === 'boolean'"
          :id="`field-${field.name}`"
          v-model="formData[field.name]"
          type="checkbox"
          class="h-4 w-4 text-blue-600 rounded border-gray-300 dark:border-gray-600 focus:ring-blue-500"
        />

        <!-- Number -->
        <input
          v-else-if="field.type === 'number'"
          :id="`field-${field.name}`"
          v-model.number="formData[field.name]"
          type="number"
          :step="field.step || 'any'"
          :min="field.min"
          :max="field.max"
          class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        <!-- Default: text -->
        <input
          v-else
          :id="`field-${field.name}`"
          v-model="formData[field.name]"
          type="text"
          :placeholder="field.description"
          class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        <!-- Field description -->
        <p v-if="field.description" class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
          {{ field.description }}
        </p>
      </div>
    </div>

    <!-- Execute Button -->
    <div v-if="formFields.length > 0" class="form-actions flex gap-2 pt-2">
      <button
        class="btn-execute px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="isExecuting"
        @click="handleExecute"
      >
        {{ isExecuting ? $t('generatedForm.executing') : $t('generatedForm.executeButton') }}
      </button>
      <button
        class="btn-reset px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        :disabled="isExecuting"
        @click="resetForm"
      >
        {{ $t('generatedForm.resetButton') }}
      </button>
    </div>

    <!-- Result -->
    <div
      v-if="result"
      class="result-panel bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3"
    >
      <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
        {{ $t('generatedForm.resultTitle') }}
      </h4>
      <pre class="text-xs text-green-600 dark:text-green-400 overflow-auto max-h-40">{{ JSON.stringify(result, null, 2) }}</pre>
    </div>

    <!-- Error -->
    <div
      v-if="execError"
      class="error-panel bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3"
    >
      <h4 class="text-sm font-semibold text-red-600 dark:text-red-400 mb-1">
        {{ $t('generatedForm.errorTitle') }}
      </h4>
      <p class="text-xs text-red-500 dark:text-red-400">{{ execError }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file GeneratedFormView.vue
 * @description Fallback form renderer for cells without a custom View.vue.
 *
 * Generates UI from the cell's properties_schema (from type.json).
 * Calls cellInstance.execute(formData) when user clicks Execute.
 * This component is THE fallback path — cellInstance.show() returns undefined
 * when no custom view is found, and useCellViewProvider assigns this component.
 */

import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'

const log = createLogger('workspace:generated-form')
const { t } = useI18n()

// ── Props ─────────────────────────────────────────────────────────────────────
const props = defineProps<{
  cellInstance: any
  schema: Record<string, any>
  cellTypeName?: string
}>()

// ── State ─────────────────────────────────────────────────────────────────────
const isExecuting = ref(false)
const result = ref<any>(null)
const execError = ref<string | null>(null)

// ── Form Field Generation ─────────────────────────────────────────────────────

interface FormField {
  name: string
  label: string
  type: 'string' | 'number' | 'boolean' | 'enum' | 'text'
  required: boolean
  description?: string
  options?: string[]
  default?: any
  min?: number
  max?: number
  step?: number
}

const formFields = computed<FormField[]>(() => {
  const properties = props.schema?.properties ?? props.schema ?? {}
  const requiredFields: string[] = props.schema?.required ?? []

  return Object.entries(properties).map(([name, def]: [string, any]) => {
    const field: FormField = {
      name,
      label: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      type: 'string',
      required: requiredFields.includes(name),
      description: def.description,
      default: def.default,
    }

    if (def.enum) {
      field.type = 'enum'
      field.options = Array.isArray(def.enum) && def.enum.length > 0 ? def.enum : []
    } else if (def.type === 'number' || def.type === 'integer') {
      field.type = 'number'
      field.min = def.minimum
      field.max = def.maximum
    } else if (def.type === 'boolean') {
      field.type = 'boolean'
    }

    return field
  })
})

// ── Form Data ─────────────────────────────────────────────────────────────────

const formData = ref<Record<string, any>>(buildDefaults())

function buildDefaults(): Record<string, any> {
  const properties = props.schema?.properties ?? props.schema ?? {}
  const defaults: Record<string, any> = {}
  for (const [name, def] of Object.entries(properties) as [string, any][]) {
    if (def.default !== undefined) {
      defaults[name] = def.default
    } else if (def.type === 'number' || def.type === 'integer') {
      defaults[name] = 0
    } else if (def.type === 'boolean') {
      defaults[name] = false
    } else if (def.enum) {
      defaults[name] = Array.isArray(def.enum) && def.enum.length > 0 ? def.enum[0] : ''
    } else {
      defaults[name] = ''
    }
  }
  return defaults
}

function resetForm(): void {
  formData.value = buildDefaults()
  result.value = null
  execError.value = null
}

// ── Execute ───────────────────────────────────────────────────────────────────

async function handleExecute(): Promise<void> {
  if (!props.cellInstance) {
    log.error('[GeneratedFormView] No cellInstance provided')
    execError.value = 'Cell instance not available'
    return
  }

  isExecuting.value = true
  result.value = null
  execError.value = null

  try {
    log.debug('[GeneratedFormView] Executing', { cellTypeName: props.cellTypeName, input: formData.value })
    const cellResult = await props.cellInstance.execute(formData.value)

    if (cellResult.success) {
      result.value = cellResult.output
      log.info('[GeneratedFormView] Execution succeeded', { cellTypeName: props.cellTypeName })
    } else {
      execError.value = cellResult.error || 'Execution failed'
      log.warn('[GeneratedFormView] Execution failed', { error: execError.value })
    }
  } catch (err: any) {
    execError.value = err?.message || 'Unexpected error during execution'
    log.error('[GeneratedFormView] Execution threw', err)
  } finally {
    isExecuting.value = false
  }
}
</script>

<style scoped>
.generated-form-view {
  background: transparent;
}

pre {
  font-family: 'Courier New', Courier, monospace;
}
</style>
