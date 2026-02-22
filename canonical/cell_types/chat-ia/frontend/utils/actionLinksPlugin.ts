/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-02-22",
 *   "console_calls_found": 17,
 *   "console_calls_migrated": 17,
 *   "migration_rate": 100,
 *   "logger_namespace": "utils:actionlinks",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Action Links Plugin for Markdown-It
 * 
 * Unified system using ```json code blocks with action key detection
 * Uses fence renderer (decorator pattern) for proper markdown-it integration
 */

import { createLogger } from '@/utils/logger'
import type MarkdownIt from 'markdown-it'
import type StateCore from 'markdown-it/lib/rules_core/state_core'
import type Token from 'markdown-it/lib/token'
import type Renderer from 'markdown-it/lib/renderer'

const log = createLogger('utils:actionlinks')

/**
 * Safely parse JSON string with detailed error handling
 * @param jsonString - JSON string to parse
 * @returns Parsed object or null on error
 */
export function safeParseJSON(jsonString: string): any {
  const DEBUG_SAFE_PARSE = process.env.NODE_ENV === 'development'
  
  if (!jsonString || typeof jsonString !== 'string') {
    if (DEBUG_SAFE_PARSE) {
      log.error('Invalid input', { type: typeof jsonString })
    }
    return null
  }
  
  try {
    const sanitized = jsonString.trim()
    
    if (DEBUG_SAFE_PARSE) {
      log.debug('Parsing JSON', { preview: sanitized.substring(0, 100) })
    }
    
    const parsed = JSON.parse(sanitized)
    
    if (DEBUG_SAFE_PARSE) {
      log.debug('Successfully parsed', { keys: Object.keys(parsed) })
    }
    
    return parsed
  } catch (error: any) {
    log.error('Failed to parse JSON', { 
      message: error.message,
      preview: jsonString.substring(0, 100),
      errorType: error.constructor.name
    })
    return null
  }
}

/**
 * Escape HTML special characters
 * @param text - Text to escape
 * @returns Escaped text
 */
function escapeHtml(text: string): string {
  if (!text) return ''
  
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  }
  
  return text.replace(/[&<>"']/g, (m) => map[m])
}

/**
 * Plugin markdown-it para processar action links via fence renderer
 * @param md - Instância do markdown-it
 */
export function actionLinksPlugin(md: MarkdownIt): void {
  // UNIFIED SYSTEM: Use markdown-it's fence renderer (decorator pattern)
  // This is the proper way to customize ```json code blocks
  
  // Store the original fence renderer
  const defaultFenceRenderer = md.renderer.rules.fence || function(tokens: Token[], idx: number, options: any, env: any, self: Renderer) {
    return self.renderToken(tokens, idx, options)
  }
  
  // Override fence renderer to detect and process JSON action blocks
  md.renderer.rules.fence = function(tokens: Token[], idx: number, options: any, env: any, self: Renderer): string {
    const token = tokens[idx]
    const info = token.info ? token.info.trim() : ''
    const langName = info ? info.split(/\s+/g)[0] : ''
    
    // Only process 'json' code blocks
    if (langName !== 'json') {
      return defaultFenceRenderer(tokens, idx, options, env, self)
    }
    
    const content = token.content.trim()
    
    log.debug('Processing JSON fence block', { 
      contentLength: content.length, 
      preview: content.substring(0, 100) 
    })
    
    try {
      // Try to parse the JSON
      const payload = safeParseJSON(content)
      
      if (!payload || Object.keys(payload).length === 0) {
        log.debug('Failed to parse JSON, rendering as standard code block')
        return defaultFenceRenderer(tokens, idx, options, env, self)
      }
      
      // Check if this is an action (has "action" key)
      if (!payload.action) {
        log.debug('No "action" key found - rendering as standard code block')
        return defaultFenceRenderer(tokens, idx, options, env, self)
      }
      
      // This is an action! Extract metadata
      const actionName = payload.action
      const label = payload.label || actionName
      const icon = payload.icon || ''
      const variant = payload.variant || 'primary'
      
      // Clean the payload by removing metadata fields
      const cleanPayload = { ...payload }
      delete cleanPayload.action
      delete cleanPayload.label
      delete cleanPayload.icon
      delete cleanPayload.variant
      
      log.debug('Detected action', { 
        actionName, 
        label, 
        icon, 
        variant, 
        payloadKeys: Object.keys(cleanPayload) 
      })
      
      // Create action-link element
      // This will be picked up by MarkdownRenderer.vue and mounted as a Vue component
      const payloadJson = JSON.stringify(cleanPayload)
      const actionLink = `<action-link action-url="action-json:${escapeHtml(actionName)}" label="${escapeHtml(label)}" ${icon ? `icon="${escapeHtml(icon)}"` : ''} ${variant ? `variant="${escapeHtml(variant)}"` : ''} data-json-action="true" data-payload="${escapeHtml(payloadJson)}" data-action-link></action-link>`
      
      return actionLink + '\n'
      
    } catch (error: any) {
      log.error('Error processing JSON fence block', error)
      // On error, render as standard code block
      return defaultFenceRenderer(tokens, idx, options, env, self)
    }
  }
}
