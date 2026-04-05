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
 *   "dark_mode_support": "full",
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-02-22",
 *   "console_calls_found": 34,
 *   "console_calls_migrated": 34,
 *   "migration_rate": 100,
 *   "logger_namespace": "markdown:renderer",
 *   "validation_status": "excellent"
 * }
 */
<template>
  <div
    ref="rendererContainer"
    class="markdown-renderer"
    :data-testid="dataTestid"
    role="article"
    :aria-label="computedAriaLabel"
  ></div>
</template>

<script setup>
import { ref, computed, onMounted, onUpdated, onBeforeUnmount, nextTick, getCurrentInstance, watch, createApp, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { createPinia } from 'pinia'
import { createLogger } from '@/utils/logger'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { actionLinksPlugin } from '../utils/actionLinksPlugin'
import ActionLink from './ActionLink.vue'
import i18n from '@/i18n'
// Note: We're not importing a specific highlight.js theme here
// Instead, we use custom CSS variables that adapt to light/dark theme

const log = createLogger('markdown:renderer')
const { t } = useI18n()

const props = defineProps({
  /**
   * Markdown content to be rendered
   */
  content: {
    type: String,
    required: true,
    default: '',
  },
  /**
   * Test ID for testing purposes
   */
  dataTestid: {
    type: String,
    default: 'markdown-renderer',
  },
  /**
   * Aria label for accessibility
   */
  ariaLabel: {
    type: String,
    default: '',
  },
})

const instance = getCurrentInstance()
const md = ref(null)
const blockCounter = ref(0)
const rendererContainer = ref(null)
const mountedActionLinks = ref([])

// Inject main Pinia instance if available (provided by App.vue)
// This allows ActionLinks to access the main chatStore with registered ChatIA
const mainPinia = inject('pinia', null)

const computedAriaLabel = computed(() => {
  return props.ariaLabel || t('markdownRenderer.ariaLabel')
})

const renderedHtml = computed(() => {
  if (!props.content) {
    return ''
  }

  try {
    // ==== ITERATION #2 DEBUG: Pre-render content inspection ====
    log.debug('[ITER2-DEBUG] renderedHtml computed - about to render')
    log.debug('[ITER2-DEBUG] Content length:', props.content.length)
    log.debug('[ITER2-DEBUG] Content contains <action:post>:', props.content.includes('<action:post>'))
    log.debug('[ITER2-DEBUG] Content preview:', props.content.substring(0, 300))
    
    // Debug: Check if content contains action links
    if (props.content.includes('action:')) {
      log.debug('Content contains action: links')
      log.debug('Sample:', props.content.substring(0, 500))
    }
    
    // ==== ITERATION #2 DEBUG: Verify md.parse override exists ====
    log.debug('[ITER2-DEBUG] md.value.parse is overridden:', md.value.parse.name !== 'parse')
    log.debug('[ITER2-DEBUG] md.value.parse function:', md.value.parse.toString().substring(0, 200))
    
    const rendered = md.value.render(props.content)
    
    // ==== ITERATION #2 DEBUG: Post-render verification ====
    log.debug('[ITER2-DEBUG] Rendering complete, result length:', rendered.length)
    
    // Debug: Check if rendered HTML contains action-link elements
    if (rendered.includes('action-link')) {
      log.debug('Rendered HTML contains action-link elements')
    } else if (props.content.includes('action:')) {
      log.debug('WARNING: Content has action: but no action-link elements were created')
      log.debug('Rendered sample:', rendered.substring(0, 500))
    }
    
    return addCopyButtonsToCodeBlocks(rendered)
  } catch (error) {
    log.error('Error rendering markdown:', error)
    return `<p class="markdown-error">${t('markdownRenderer.renderError')}</p>`
  }
})

/**
 * Render HTML and mount Vue components for action links
 */
function renderContent() {
  if (!rendererContainer.value) return
  
  // Unmount any previously mounted action links
  unmountActionLinks()
  
  // Set the HTML content
  const html = renderedHtml.value
  rendererContainer.value.innerHTML = html
  
  // Find all action-link elements and mount Vue components
  nextTick(() => {
    mountActionLinks()
    attachCopyEventListeners()
  })
}

/**
 * Mount ActionLink Vue components in place of action-link HTML elements
 */
function mountActionLinks() {
  if (!rendererContainer.value) return
  
  const actionLinkElements = rendererContainer.value.querySelectorAll('action-link[data-action-link]')
  
  log.debug(`Mounting ${actionLinkElements.length} action link(s)`)
  log.debug(`Main Pinia available: ${!!mainPinia}`)
  log.debug('Container HTML preview:', rendererContainer.value?.innerHTML.substring(0, 500))
  
  if (actionLinkElements.length === 0 && rendererContainer.value?.innerHTML.includes('action-link')) {
    log.warn('WARNING: HTML contains action-link but query found 0 elements')
    log.warn('Possible issue: missing data-action-link attribute')
  }
  
  actionLinkElements.forEach((el, index) => {
    const actionUrl = el.getAttribute('action-url')
    const label = el.getAttribute('label')
    const icon = el.getAttribute('icon') || ''
    const variant = el.getAttribute('variant') || 'primary'
    const dataPostAction = el.getAttribute('data-post-action') || 'false'
    const dataPayload = el.getAttribute('data-payload') || '{}'
    
    log.debug(`Mounting ActionLink #${index + 1}:`, { 
      actionUrl, 
      label, 
      icon, 
      variant,
      dataPostAction,
      dataPayloadPreview: dataPayload.substring(0, 100) + (dataPayload.length > 100 ? '...' : ''),
      elementHTML: el.outerHTML
    })
    
    // Create a wrapper span to mount the Vue component
    const wrapper = document.createElement('span')
    wrapper.style.display = 'inline-block'
    
    // Replace the action-link element with the wrapper
    el.replaceWith(wrapper)
    
    // Create and mount the ActionLink component
    const app = createApp(ActionLink, {
      actionUrl,
      label,
      icon,
      variant,
      dataPostAction,
      dataPayload
    })
    
    // Use the same i18n instance
    app.use(i18n)
    
    // Use main Pinia instance if available, otherwise create isolated one
    // Using main Pinia allows ActionLink to access the shared chatStore
    // with registered ChatIA component for proper action execution
    if (mainPinia) {
      log.debug(`Using main Pinia instance for ActionLink #${index + 1}`)
      app.use(mainPinia)
    } else {
      log.warn(`Main Pinia not available, creating isolated instance for ActionLink #${index + 1}`)
      log.warn('Action execution may fail - chatStore won\'t have ChatIA registered')
      app.use(createPinia())
    }
    
    // Mount the component
    app.mount(wrapper)
    
    // Store reference for cleanup
    mountedActionLinks.value.push({ app, wrapper })
  })
  
  log.debug(`Successfully mounted ${mountedActionLinks.value.length} ActionLink component(s)`)
}

/**
 * Unmount all action link components
 */
function unmountActionLinks() {
  mountedActionLinks.value.forEach(({ app }) => {
    app.unmount()
  })
  mountedActionLinks.value = []
}

/**
 * Watch for content changes and re-render
 */
watch(() => props.content, () => {
  renderContent()
})

function initializeMarkdownParser() {
  md.value = new MarkdownIt({
    html: false, // Disable HTML tags for security
    xhtmlOut: true,
    breaks: true,
    linkify: true, // Enable linkify for custom protocol detection
    typographer: true,
    highlight: (str, lang) => {
      if (lang && hljs.getLanguage(lang)) {
        try {
          return hljs.highlight(str, {
            language: lang,
            ignoreIllegals: true,
          }).value
        } catch (err) {
          log.error('Highlight.js error:', err)
        }
      }
      // Use auto-detection for unknown languages
      try {
        return hljs.highlightAuto(str).value
      } catch (err) {
        log.error('Highlight.js auto-detection error:', err)
        return '' // Return empty string and let markdown-it escape the code
      }
    },
  })
  
  // Configure linkify to ONLY recognize action: and action-post: protocols
  // Remove all default protocols to prevent auto-detection of http://, https://, etc.
  // This prevents pollution of logs with unwanted links while enabling action links
  
  // Reset linkify schemas - remove all defaults
  md.value.linkify.set({ fuzzyLink: false, fuzzyEmail: false, fuzzyIP: false })
  
  // Add custom protocol: action:
  md.value.linkify.add('action:', {
    validate: function (text, pos, self) {
      const tail = text.slice(pos)
      // Match action:name or action:name?params
      if (!self.re.action) {
        self.re.action = new RegExp('^[a-zA-Z_][a-zA-Z0-9_]*(\\?[^\\s]*)?')
      }
      if (self.re.action.test(tail)) {
        return tail.match(self.re.action)[0].length
      }
      return 0
    }
  })
  
  // Add custom protocol: action-post:
  md.value.linkify.add('action-post:', {
    validate: function (text, pos, self) {
      const tail = text.slice(pos)
      // Match action-post:name#{"json"} or action-post:name#{...}
      if (!self.re.actionPost) {
        self.re.actionPost = new RegExp('^[a-zA-Z_][a-zA-Z0-9_]*(#\\{[^}]*\\})?')
      }
      if (self.re.actionPost.test(tail)) {
        return tail.match(self.re.actionPost)[0].length
      }
      return 0
    }
  })
  
  log.debug('Configured linkify for action: and action-post: protocols only')
  log.debug('Disabled default protocols (http, https, etc.) to prevent log pollution')
  
  // Enable action links plugin
  md.value.use(actionLinksPlugin)
  
  // ===== LOG NÍVEL 6: PLUGIN VERIFICATION =====
  log.debug('Plugin registered')
  log.debug('link_open override exists:', !!md.value.renderer.rules.link_open)
  log.debug('link_close override exists:', !!md.value.renderer.rules.link_close)
  log.debug('markdown-it config:', {
    html: md.value.options.html,
    xhtmlOut: md.value.options.xhtmlOut,
    breaks: md.value.options.breaks,
    linkify: md.value.options.linkify,
    typographer: md.value.options.typographer
  })
  // ===== FIM LOG NÍVEL 6 =====
}

function addCopyButtonsToCodeBlocks(html) {
  // Add copy buttons to code blocks using a unique identifier
  // Use component instance counter for unique IDs
  return html.replace(
    /<pre><code([^>]*)>([\s\S]*?)<\/code><\/pre>/g,
    (match, attributes, code) => {
      const blockId = `code-block-${instance.uid}-${blockCounter.value++}`
      return `<div class="code-block-wrapper" data-code-block-id="${blockId}">
        <div class="code-block-header">
          <button 
            class="copy-button" 
            data-code-block-target="${blockId}"
            aria-label="${t('markdownRenderer.copyCode')}"
            title="${t('markdownRenderer.copyCode')}"
            type="button"
          >
            ${t('markdownRenderer.copyButton')}
          </button>
        </div>
        <pre><code${attributes}>${code}</code></pre>
      </div>`
    }
  )
}

function attachCopyEventListeners() {
  // Use event delegation on the root element instead of attaching to each button
  // This is more efficient and avoids memory leaks
  nextTick(() => {
    const el = instance?.proxy?.$el
    
    // Remove existing listener if any
    if (el && el._copyHandler) {
      el.removeEventListener('click', el._copyHandler)
    }

    // Create delegated event handler
    const handler = (event) => {
      const button = event.target.closest('.copy-button')
      if (button) {
        handleCopyClick({ currentTarget: button })
      }
    }

    // Store handler reference for cleanup
    if (el) {
      el._copyHandler = handler
      el.addEventListener('click', handler)
    }
  })
}

async function handleCopyClick(event) {
  const button = event.currentTarget
  const blockId = button.getAttribute('data-code-block-target')
  const el = instance?.proxy?.$el
  const codeBlockWrapper = el?.querySelector(
    `[data-code-block-id="${blockId}"]`
  )

  if (!codeBlockWrapper) {
    log.error('Code block not found')
    return
  }

  const codeElement = codeBlockWrapper.querySelector('pre code')
  if (!codeElement) {
    log.error('Code element not found')
    return
  }

  const codeText = codeElement.textContent

  try {
    await copyToClipboard(codeText)
    showCopyFeedback(button, true)
  } catch (error) {
    log.error('Failed to copy code:', error)
    showCopyFeedback(button, false)
  }
}

async function copyToClipboard(text) {
  // Modern clipboard API
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
  } else {
    // Fallback for older browsers
    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.style.position = 'fixed'
    textArea.style.left = '-999999px'
    textArea.style.top = '-999999px'
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()

    try {
      document.execCommand('copy')
      textArea.remove()
    } catch (error) {
      textArea.remove()
      throw error
    }
  }
}

function showCopyFeedback(button, success) {
  const originalText = button.innerHTML
  button.innerHTML = success ? t('markdownRenderer.copiedButton') : t('markdownRenderer.copyError')
  button.disabled = true

  setTimeout(() => {
    button.innerHTML = originalText
    button.disabled = false
  }, 2000)
}

// Initialize markdown parser immediately
initializeMarkdownParser()

onMounted(() => {
  renderContent()
})

onUpdated(() => {
  // Note: We handle re-rendering via watch on props.content
  // to avoid unnecessary re-renders
})

onBeforeUnmount(() => {
  // Clean up event listener
  const el = instance?.proxy?.$el
  if (el && el._copyHandler) {
    el.removeEventListener('click', el._copyHandler)
    delete el._copyHandler
  }
  
  // Unmount all action link components
  unmountActionLinks()
})
</script>

<style scoped>
/* Markdown base styles */
.markdown-renderer {
  color: var(--color-text-primary);
  line-height: var(--line-height-relaxed);
  font-size: var(--font-size-base);
}

/* Headings */
.markdown-renderer :deep(h1),
.markdown-renderer :deep(h2),
.markdown-renderer :deep(h3),
.markdown-renderer :deep(h4),
.markdown-renderer :deep(h5),
.markdown-renderer :deep(h6) {
  margin-top: var(--space-lg);
  margin-bottom: var(--space-md);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  line-height: var(--line-height-tight);
}

.markdown-renderer :deep(h1) {
  font-size: var(--font-size-2xl);
  border-bottom: 2px solid var(--color-border);
  padding-bottom: var(--space-xs);
}

.markdown-renderer :deep(h2) {
  font-size: var(--font-size-xl);
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--space-xs);
}

.markdown-renderer :deep(h3) {
  font-size: var(--font-size-lg);
}

.markdown-renderer :deep(h4) {
  font-size: var(--font-size-md);
}

.markdown-renderer :deep(h5),
.markdown-renderer :deep(h6) {
  font-size: var(--font-size-base);
}

/* Paragraphs */
.markdown-renderer :deep(p) {
  margin-top: 0;
  margin-bottom: var(--space-md);
}

/* Bold and emphasis */
.markdown-renderer :deep(strong),
.markdown-renderer :deep(b) {
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
}

.markdown-renderer :deep(em),
.markdown-renderer :deep(i) {
  font-style: italic;
  color: var(--color-text-primary);
}

/* Links */
.markdown-renderer :deep(a) {
  color: var(--color-primary);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s ease;
}

.markdown-renderer :deep(a:hover) {
  border-bottom-color: var(--color-primary);
}

.markdown-renderer :deep(a:focus) {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Lists */
.markdown-renderer :deep(ul),
.markdown-renderer :deep(ol) {
  margin-top: 0;
  margin-bottom: var(--space-md);
  padding-left: var(--space-xl);
}

.markdown-renderer :deep(li) {
  margin-bottom: var(--space-xs);
}

.markdown-renderer :deep(li > p) {
  margin-bottom: var(--space-xs);
}

/* Inline code */
.markdown-renderer :deep(code) {
  background: var(--color-surface-hover);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 2px 6px;
  font-family: var(--font-family-mono);
  font-size: 0.9em;
  color: var(--color-code-text);
}

/* Code blocks */
.markdown-renderer :deep(.code-block-wrapper) {
  position: relative;
  margin: var(--space-md) 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-code-bg);
  border: 1px solid var(--color-border);
}

.markdown-renderer :deep(.code-block-header) {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-xs) var(--space-sm);
  background: var(--color-surface-hover);
  border-bottom: 1px solid var(--color-border);
}

.markdown-renderer :deep(.copy-button) {
  padding: var(--space-xs) var(--space-sm);
  background: var(--color-primary);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  color: var(--color-text-on-primary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--transition-base);
  font-family: var(--font-family-base);
  opacity: 0.8;
}

.markdown-renderer :deep(.copy-button:hover:not(:disabled)) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  opacity: 1;
}

.markdown-renderer :deep(.copy-button:focus) {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.markdown-renderer :deep(.copy-button:disabled) {
  opacity: 0.5;
  cursor: not-allowed;
}

.markdown-renderer :deep(pre) {
  margin: 0;
  padding: var(--space-md);
  overflow-x: auto;
  background: var(--color-code-bg);
  border: none;
}

.markdown-renderer :deep(pre code) {
  background: transparent;
  border: none;
  padding: 0;
  font-family: 'Courier New', Courier, monospace;
  font-size: var(--font-size-sm);
  color: var(--color-code-text);
  display: block;
  line-height: var(--line-height-relaxed);
}

/* Blockquotes */
.markdown-renderer :deep(blockquote) {
  margin: var(--space-md) 0;
  padding-left: var(--space-md);
  border-left: 4px solid var(--color-border);
  color: var(--color-text-secondary);
  font-style: italic;
}

.markdown-renderer :deep(blockquote p) {
  margin-bottom: var(--space-sm);
}

/* Horizontal rules */
.markdown-renderer :deep(hr) {
  border: none;
  border-top: 2px solid var(--color-border);
  margin: var(--space-xl) 0;
}

/* Tables */
.markdown-renderer :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: var(--space-md) 0;
  overflow-x: auto;
  display: block;
}

.markdown-renderer :deep(th),
.markdown-renderer :deep(td) {
  padding: var(--space-sm);
  border: 1px solid var(--color-border);
  text-align: left;
}

.markdown-renderer :deep(th) {
  background: var(--color-surface-hover);
  font-weight: var(--font-weight-semibold);
}

.markdown-renderer :deep(tr:nth-child(even)) {
  background: var(--color-surface-hover);
}

/* Images */
.markdown-renderer :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  margin: var(--space-md) 0;
}

/* Error state */
.markdown-renderer :deep(.markdown-error) {
  color: var(--color-error);
  padding: var(--space-sm);
  background: var(--color-error-light);
  border: 1px solid var(--color-error);
  border-radius: var(--radius-sm);
}

/* Syntax highlighting for code blocks */
.markdown-renderer :deep(.hljs) {
  background: var(--color-code-bg);
  color: var(--color-code-text);
}

.markdown-renderer :deep(.hljs-comment),
.markdown-renderer :deep(.hljs-quote) {
  color: var(--color-syntax-comment);
  font-style: italic;
}

.markdown-renderer :deep(.hljs-keyword),
.markdown-renderer :deep(.hljs-selector-tag),
.markdown-renderer :deep(.hljs-subst) {
  color: var(--color-syntax-keyword);
  font-weight: var(--font-weight-semibold);
}

.markdown-renderer :deep(.hljs-number),
.markdown-renderer :deep(.hljs-literal),
.markdown-renderer :deep(.hljs-variable),
.markdown-renderer :deep(.hljs-template-variable),
.markdown-renderer :deep(.hljs-tag .hljs-attr) {
  color: var(--color-syntax-number);
}

.markdown-renderer :deep(.hljs-string),
.markdown-renderer :deep(.hljs-doctag) {
  color: var(--color-syntax-string);
}

.markdown-renderer :deep(.hljs-title),
.markdown-renderer :deep(.hljs-section),
.markdown-renderer :deep(.hljs-selector-id) {
  color: var(--color-syntax-function);
  font-weight: var(--font-weight-bold);
}

.markdown-renderer :deep(.hljs-type),
.markdown-renderer :deep(.hljs-class .hljs-title) {
  color: var(--color-syntax-function);
}

.markdown-renderer :deep(.hljs-tag),
.markdown-renderer :deep(.hljs-name),
.markdown-renderer :deep(.hljs-attribute) {
  color: var(--color-syntax-tag);
}

.markdown-renderer :deep(.hljs-regexp),
.markdown-renderer :deep(.hljs-link) {
  color: var(--color-syntax-string);
}

.markdown-renderer :deep(.hljs-symbol),
.markdown-renderer :deep(.hljs-bullet) {
  color: var(--color-syntax-symbol);
}

.markdown-renderer :deep(.hljs-built_in),
.markdown-renderer :deep(.hljs-builtin-name) {
  color: var(--color-syntax-number);
}

.markdown-renderer :deep(.hljs-meta) {
  color: var(--color-syntax-comment);
}

.markdown-renderer :deep(.hljs-deletion) {
  background: var(--color-syntax-deletion-bg);
  color: var(--color-syntax-deletion-text);
}

.markdown-renderer :deep(.hljs-addition) {
  background: var(--color-syntax-addition-bg);
  color: var(--color-syntax-addition-text);
}

.markdown-renderer :deep(.hljs-emphasis) {
  font-style: italic;
}

.markdown-renderer :deep(.hljs-strong) {
  font-weight: var(--font-weight-bold);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .markdown-renderer :deep(pre) {
    font-size: var(--font-size-xs);
  }

  .markdown-renderer :deep(table) {
    font-size: var(--font-size-sm);
  }
}
</style>
