/**
 * Chat IA - Configuration for size limits and constraints
 *
 * Defines limits for prompts and attachments to ensure optimal
 * AI model performance and prevent token overflow.
 */

/**
 * Maximum characters allowed in the prompt textarea
 * Based on typical LLM context windows and token limits
 *
 * Mistral/Ollama models: ~8k tokens ≈ 32k chars
 * Gemini: ~30k tokens ≈ 120k chars
 *
 * Setting a conservative limit to leave room for:
 * - Conversation history
 * - System prompts
 * - Attachments content
 */
export const PROMPT_MAX_CHARS = 10000

/**
 * Maximum size for a single attachment in bytes
 * Default: 500KB per attachment
 *
 * This prevents sending excessively large files that would
 * consume too many tokens or cause API timeouts
 */
export const ATTACHMENT_MAX_SIZE = 500 * 1024 // 500KB

/**
 * Maximum total size for all attachments combined in bytes
 * Default: 2MB total
 *
 * Ensures the entire request stays within reasonable limits
 * for network transfer and model processing
 */
export const ATTACHMENTS_TOTAL_MAX_SIZE = 2 * 1024 * 1024 // 2MB

/**
 * Maximum number of attachments allowed in a single message
 * Default: 10 attachments
 *
 * Prevents excessive attachment lists while allowing
 * reasonable multi-file scenarios
 */
export const MAX_ATTACHMENTS = 10

/**
 * Warning threshold for prompt length (percentage)
 * Show warning when prompt reaches this percentage of max
 * Default: 80%
 */
export const PROMPT_WARNING_THRESHOLD = 0.8

/**
 * Warning threshold for attachment size (percentage)
 * Show warning when total attachments reach this percentage of max
 * Default: 80%
 */
export const ATTACHMENT_WARNING_THRESHOLD = 0.8

/**
 * Format bytes to human-readable string
 * @param {number} bytes - Size in bytes
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted size string
 */
export function formatBytes(bytes, decimals = 2) {
  if (bytes === 0) return '0 Bytes'

  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB']

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

/**
 * Validate attachment size
 * @param {number} size - Size in bytes
 * @returns {{ valid: boolean, message: string }}
 */
export function validateAttachmentSize(size) {
  if (size > ATTACHMENT_MAX_SIZE) {
    return {
      valid: false,
      message: `Arquivo muito grande. Máximo: ${formatBytes(ATTACHMENT_MAX_SIZE)}`,
    }
  }
  return { valid: true, message: '' }
}

/**
 * Validate total attachments size
 * @param {Array} attachments - Array of attachments with size property
 * @returns {{ valid: boolean, message: string, totalSize: number }}
 */
export function validateTotalAttachmentsSize(attachments) {
  const totalSize = attachments.reduce((sum, att) => sum + (att.size || 0), 0)

  if (totalSize > ATTACHMENTS_TOTAL_MAX_SIZE) {
    return {
      valid: false,
      message: `Total de anexos muito grande. Máximo: ${formatBytes(ATTACHMENTS_TOTAL_MAX_SIZE)}`,
      totalSize,
    }
  }

  return { valid: true, message: '', totalSize }
}

/**
 * Validate prompt length
 * @param {string} prompt - Prompt text
 * @returns {{ valid: boolean, message: string, length: number }}
 */
export function validatePromptLength(prompt) {
  const length = prompt.length

  if (length > PROMPT_MAX_CHARS) {
    return {
      valid: false,
      message: `Prompt muito longo. Máximo: ${PROMPT_MAX_CHARS.toLocaleString()} caracteres`,
      length,
    }
  }

  return { valid: true, message: '', length }
}
