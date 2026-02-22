/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "dark_mode_support": "full",
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-02-22",
 *   "console_calls_found": 16,
 *   "console_calls_migrated": 16,
 *   "migration_rate": 100,
 *   "logger_namespace": "chat:actionlink",
 *   "validation_status": "excellent"
 * }
 */
<template>
  <!-- Adaptive rendering based on user role -->
  <div v-if="isJsonAction" class="action-json-wrapper">
    <!-- Admin/Manager view: Show JSON + Execute button -->
    <div v-if="isAdmin" class="flex flex-col gap-2 p-3 border rounded-md" :class="borderColorClass">
      <div class="flex items-center justify-between">
        <span class="text-xs font-semibold uppercase text-text-secondary dark:text-text-secondary-dark">
          {{ t('admin.actionLink.actionDefinition') }}
        </span>
        <button
          :class="[
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium',
            'transition-all duration-200',
            'border',
            variantClasses,
            { 'opacity-50 cursor-not-allowed': loading }
          ]"
          :disabled="loading"
          :aria-label="ariaLabel"
          @click="handleClick"
        >
          <span v-if="loading" class="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
          <span v-else-if="icon">{{ icon }}</span>
          <span>{{ label }}</span>
        </button>
      </div>
      
      <!-- Pretty-printed JSON with syntax highlighting -->
      <pre class="p-2 rounded bg-surface dark:bg-surface-dark text-xs overflow-x-auto overflow-y-auto max-h-[400px]">
        <code class="whitespace-pre-wrap break-words">{{ prettyJson }}</code>
      </pre>
      
      <!-- Tooltip/Help text -->
      <div class="text-xs text-text-secondary dark:text-text-secondary-dark">
        <span>{{ t('admin.actionLink.inspectAndExecute') }}</span>
      </div>
    </div>
    
    <!-- Layperson view: Simple button only -->
    <button
      v-else
      :class="[
        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium',
        'transition-all duration-200 cursor-pointer',
        'border',
        variantClasses,
        { 'opacity-50 cursor-not-allowed': loading }
      ]"
      :disabled="loading"
      :aria-label="ariaLabel"
      @click="handleClick"
    >
      <span v-if="loading" class="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
      <span v-else-if="icon">{{ icon }}</span>
      <span>{{ label }}</span>
    </button>
  </div>
  
  <!-- Legacy GET actions: Always simple button -->
  <button
    v-else
    :class="[
      'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium',
      'transition-all duration-200 cursor-pointer',
      'border',
      variantClasses,
      { 'opacity-50 cursor-not-allowed': loading }
    ]"
    :disabled="loading"
    :aria-label="ariaLabel"
    @click="handleClick"
  >
    <span v-if="loading" class="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
    <span v-else-if="icon">{{ icon }}</span>
    <span>{{ label }}</span>
  </button>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import { executeAction, parseActionURL, hasAction, isProposalAction } from '@/composables/useActionRegistry'
import { safeParseJSON } from '../utils/actionLinksPlugin'
import { useChatStore } from '@/stores/chat'
import { usePermissionsStore } from '@/stores/permissions'

const log = createLogger('chat:actionlink')
const { t } = useI18n()
const permissionsStore = usePermissionsStore()

// Constants for action handling
const DEFAULT_CONTEXT_LINES = 3

const props = defineProps({
  /**
   * URL da ação no formato action:name?params ou action-post:name
   */
  actionUrl: {
    type: String,
    required: true
  },
  
  /**
   * Texto do link
   */
  label: {
    type: String,
    required: true
  },
  
  /**
   * Ícone emoji (opcional)
   */
  icon: {
    type: String,
    default: ''
  },
  
  /**
   * Variante visual
   */
  variant: {
    type: String,
    default: 'primary', // primary, secondary, success, warning, danger
    validator: (v) => ['primary', 'secondary', 'success', 'warning', 'danger'].includes(v)
  },
  
  /**
   * Indica se é uma ação POST (data attribute do plugin - legacy)
   */
  dataPostAction: {
    type: String,
    default: 'false'
  },
  
  /**
   * Indica se é uma ação JSON (data attribute do plugin - new unified system)
   */
  dataJsonAction: {
    type: String,
    default: 'false'
  },
  
  /**
   * Payload JSON para ações POST/JSON (data attribute do plugin)
   */
  dataPayload: {
    type: String,
    default: '{}'
  }
})

const emit = defineEmits(['executed', 'error'])

const chatStore = useChatStore()

// Log chatStore state for debugging
log.debug('Component initialized', {
  chatStoreId: chatStore.$id,
  hasChatStore: !!chatStore
})

const loading = ref(false)
const error = ref(null)

// Enhanced logging for action debugging
log.debug('Component props', {
  actionUrl: props.actionUrl,
  label: props.label,
  icon: props.icon,
  variant: props.variant,
  dataPostAction: props.dataPostAction,
  dataJsonAction: props.dataJsonAction,
  payloadPreview: props.dataPayload?.substring(0, 100) + (props.dataPayload?.length > 100 ? '...' : '')
})

// Computed: is this a POST/JSON action?
const isPostAction = computed(() => {
  // Extract action name from URL
  let actionName = ''
  if (props.actionUrl.startsWith('action-post:')) {
    actionName = props.actionUrl.replace('action-post:', '')
  } else if (props.actionUrl.startsWith('action-json:')) {
    actionName = props.actionUrl.replace('action-json:', '')
  } else if (props.actionUrl.startsWith('action:')) {
    // Pure GET action - always route to GET handler
    return false
  }
  
  // Check if action is registered in the action registry
  if (hasAction(actionName)) {
    // Use registry metadata to determine if it's a POST/proposal action
    const isProposal = isProposalAction(actionName)
    log.debug('Action found in registry', {
      actionName,
      isProposal,
      routing: isProposal ? 'POST handler' : 'GET handler'
    })
    return isProposal
  }
  
  // Fallback: Check URL prefix for unregistered actions
  const result = props.dataJsonAction === 'true' || props.dataPostAction === 'true' || props.actionUrl.startsWith('action-post:')
  log.debug('Action not in registry, using URL prefix', {
    result,
    actionName,
    dataPostAction: props.dataPostAction,
    dataJsonAction: props.dataJsonAction,
    actionUrl: props.actionUrl
  })
  return result
})

// Computed: parsed payload for POST actions
const payload = computed(() => {
  const parsed = safeParseJSON(props.dataPayload)
  log.debug('Parsed payload', {
    rawPreview: props.dataPayload?.substring(0, 100),
    parsedKeys: Object.keys(parsed)
  })
  return parsed
})

// Computed: is this a JSON-based action (new unified system)?
const isJsonAction = computed(() => {
  return props.dataJsonAction === 'true' || props.actionUrl.startsWith('action-json:')
})

// Computed: is the current user an admin?
const isAdmin = computed(() => {
  return permissionsStore.isAdmin
})

// Computed: pretty-printed JSON for admin view
const prettyJson = computed(() => {
  if (!payload.value || Object.keys(payload.value).length === 0) {
    return '{}'
  }
  return JSON.stringify(payload.value, null, 2)
})

// Computed: border color for admin JSON view based on variant
const borderColorClass = computed(() => {
  const borderColors = {
    primary: 'border-primary/30 dark:border-primary-dark/30',
    secondary: 'border-border dark:border-border-dark',
    success: 'border-success/30 dark:border-success-dark/30',
    warning: 'border-warning/30 dark:border-warning-dark/30',
    danger: 'border-danger/30 dark:border-danger-dark/30'
  }
  return borderColors[props.variant] || borderColors.primary
})

const variantClasses = computed(() => {
  const variants = {
    primary: 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20 dark:bg-primary-dark/10 dark:border-primary-dark/30 dark:text-primary-dark',
    secondary: 'bg-surface border-border text-text-primary hover:bg-surface-hover dark:bg-surface-dark dark:border-border-dark dark:text-text-primary-dark',
    success: 'bg-success/10 border-success/30 text-success hover:bg-success/20 dark:bg-success-dark/10 dark:border-success-dark/30 dark:text-success-dark',
    warning: 'bg-warning/10 border-warning/30 text-warning hover:bg-warning/20 dark:bg-warning-dark/10 dark:border-warning-dark/30 dark:text-warning-dark',
    danger: 'bg-danger/10 border-danger/30 text-danger hover:bg-danger/20 dark:bg-danger-dark/10 dark:border-danger-dark/30 dark:text-danger-dark'
  }
  
  return variants[props.variant] || variants.primary
})

const ariaLabel = computed(() => {
  return t('admin.actionLink.executeAction', { action: props.label })
})

async function handleClick() {
  if (loading.value) return
  
  loading.value = true
  error.value = null
  
  try {
    if (isPostAction.value) {
      // POST MODE: Execute POST request
      await handlePostAction()
    } else {
      // GET MODE: Execute via action registry (existing logic)
      await handleGetAction()
    }
  } catch (err) {
    error.value = err.message
    emit('error', err)
    log.error('Action execution failed', {
      error: err.message,
      actionUrl: props.actionUrl,
      isPostAction: isPostAction.value
    }, err)
  } finally {
    loading.value = false
  }
}

/**
 * Handle GET-based actions (existing logic)
 */
async function handleGetAction() {
  let name, params
  
  // Handle both action: and action-json: URLs
  if (props.actionUrl.startsWith('action-json:')) {
    // For JSON actions routed through GET handler (tooling actions)
    name = props.actionUrl.replace('action-json:', '')
    // Use the payload as params
    params = { ...payload.value }
    
    log.debug('JSON action', { name, params, actionUrl: props.actionUrl })
  } else {
    // Parse action URL (traditional action: format)
    const parsed = parseActionURL(props.actionUrl)
    name = parsed.name
    params = parsed.params
    
    log.debug('Action details', { name, params, actionUrl: props.actionUrl })
  }
  
  // Execute action with context
  const context = {
    chatStore
  }
  
  log.debug('Execution context', {
    hasChatStore: !!context.chatStore,
    chatStoreId: context.chatStore?.$id
  })
  
  const result = await executeAction(name, params, context)
  
  log.info('Action executed successfully', { name, result })
  
  emit('executed', { name, params, result })
}

/**
 * Handle POST-based actions (proposal actions via registry)
 * Supports both legacy action-post: and new action-json: URLs
 */
async function handlePostAction() {
  // Handle both legacy action-post: and new action-json: formats
  const actionName = props.actionUrl
    .replace('action-post:', '')
    .replace('action-json:', '')
  
  log.debug('POST action', { actionName, payload: payload.value })
  
  // Verify action is registered as a proposal action
  if (!hasAction(actionName)) {
    throw new Error(`Action not registered: ${actionName}`)
  }
  
  if (!isProposalAction(actionName)) {
    throw new Error(`Action is not a proposal action: ${actionName}`)
  }
  
  // Execute the proposal action via registry
  // The registry handler will take care of showing the modal
  const context = {
    chatStore
  }
  
  log.debug('Executing via registry', {
    actionName,
    params: payload.value,
    hasContext: !!context.chatStore
  })
  
  const result = await executeAction(actionName, payload.value, context)
  
  log.info('Action executed successfully', { actionName, result })
  
  emit('executed', { name: actionName, params: payload.value, result })
}
</script>

<style scoped>
/* Animação de loading */
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
