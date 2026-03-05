/**
 * Utility functions for Action Registry
 * 
 * Helper functions used by action handlers for output formatting,
 * content processing, and strategy decisions.
 */

import { createLogger } from '@/utils/logger'

const log = createLogger('action:utils')

// ========================================
// OUTPUT STRATEGY CONFIGURATION
// ========================================

/**
 * Limits for intelligent output strategy
 */
export const OUTPUT_STRATEGY_LIMITS = {
  CHARS_THRESHOLD: 200,
  LINES_THRESHOLD: 5,
  MAX_PREVIEW_LINES: 100,  // Maximum lines to show before truncating
  MAX_PREVIEW_CHARS: 50000  // Maximum characters to show before truncating
}

/**
 * Determine if content should be attached vs inserted
 * @param {string} content - Content to evaluate
 * @returns {boolean} True if should attach, false if should insert
 */
export function shouldUseAttachment(content) {
  const charCount = content.length
  const lineCount = content.split('\n').length
  
  return charCount >= OUTPUT_STRATEGY_LIMITS.CHARS_THRESHOLD || 
         lineCount >= OUTPUT_STRATEGY_LIMITS.LINES_THRESHOLD
}

/**
 * Truncate content intelligently if it exceeds limits
 * @param {string} content - Content to potentially truncate
 * @param {string} type - Type of content ('grep' or 'find')
 * @returns {Object} { content: string, wasTruncated: boolean, originalSize: number }
 */
export function truncateIfNeeded(content, type) {
  const lines = content.split('\n')
  const chars = content.length
  
  let wasTruncated = false
  let truncatedContent = content
  
  // Check if truncation is needed
  if (lines.length > OUTPUT_STRATEGY_LIMITS.MAX_PREVIEW_LINES || 
      chars > OUTPUT_STRATEGY_LIMITS.MAX_PREVIEW_CHARS) {
    
    wasTruncated = true
    
    // Truncate by lines first
    const maxLines = OUTPUT_STRATEGY_LIMITS.MAX_PREVIEW_LINES
    let truncatedLines = lines.slice(0, maxLines)
    truncatedContent = truncatedLines.join('\n')
    
    // If still too long by characters, truncate by chars
    if (truncatedContent.length > OUTPUT_STRATEGY_LIMITS.MAX_PREVIEW_CHARS) {
      truncatedContent = truncatedContent.substring(0, OUTPUT_STRATEGY_LIMITS.MAX_PREVIEW_CHARS)
    }
    
    // Add truncation notice
    const omittedLines = lines.length - truncatedLines.length
    const omittedChars = chars - truncatedContent.length
    
    truncatedContent += `\n\n⚠️ Resultado truncado para visualização`
    truncatedContent += `\n   Linhas omitidas: ${omittedLines.toLocaleString()}`
    truncatedContent += `\n   Caracteres omitidos: ${omittedChars.toLocaleString()}`
    truncatedContent += `\n   Total original: ${lines.length.toLocaleString()} linhas, ${chars.toLocaleString()} caracteres`
    
    if (type === 'grep') {
      truncatedContent += `\n   Dica: Use parâmetros mais específicos para reduzir resultados`
    } else if (type === 'find') {
      truncatedContent += `\n   Dica: Use um path mais específico ou pattern mais restritivo`
    }
  }
  
  return {
    content: truncatedContent,
    wasTruncated,
    originalSize: chars,
    originalLines: lines.length,
    truncatedSize: truncatedContent.length,
    truncatedLines: truncatedContent.split('\n').length
  }
}

/**
 * Format grep search results
 * @param {Object} data - Grep response data
 * @param {string} pattern - Search pattern
 * @returns {string} Formatted content
 */
export function formatGrepResults(data, pattern) {
  const { matches, count, truncated } = data
  
  if (!matches || matches.length === 0) {
    return `📝 Nenhum resultado encontrado para "${pattern}"`
  }
  
  let result = `📝 Resultados da busca por "${pattern}":\n\n`
  
  const fileGroups = {}
  matches.forEach(match => {
    if (!fileGroups[match.file]) {
      fileGroups[match.file] = []
    }
    fileGroups[match.file].push(match)
  })
  
  Object.entries(fileGroups).forEach(([file, fileMatches]) => {
    result += `📄 ${file}:\n`
    fileMatches.forEach(match => {
      result += `  ${match.line}: ${match.content}\n`
    })
    result += '\n'
  })
  
  result += `Total: ${count} resultado(s) em ${Object.keys(fileGroups).length} arquivo(s)`
  
  if (truncated) {
    result += ' (resultados truncados)'
  }
  
  return result
}

/**
 * Format find search results
 * @param {Object} data - Find response data
 * @param {string} pattern - Search pattern
 * @returns {string} Formatted content
 */
export function formatFindResults(data, pattern) {
  const { matches, count } = data
  
  if (!matches || matches.length === 0) {
    return `📁 Nenhum arquivo encontrado para "${pattern}"`
  }
  
  let result = `📁 Arquivos encontrados para "${pattern}":\n\n`
  
  matches.forEach(match => {
    const icon = match.type === 'directory' ? '📂' : '📄'
    const sizeInfo = match.size !== null ? ` (${formatFileSize(match.size)})` : ''
    result += `${icon} ${match.path}${sizeInfo}\n`
  })
  
  result += `\nTotal: ${count} item(s)`
  
  return result
}

/**
 * Format file size to human-readable string
 * @param {number} bytes - Size in bytes
 * @returns {string} Formatted size
 */
export function formatFileSize(bytes) {
  // Input validation
  if (typeof bytes !== 'number' || bytes < 0 || !Number.isFinite(bytes)) {
    return '0 B'
  }
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1)
  
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

/**
 * Safely decode URI component, handling already-decoded content
 * @param {string} value - Value to decode
 * @returns {string} Decoded value or original if already decoded
 */
export function safeDecodeURIComponent(value) {
  if (!value) return value
  
  try {
    // Try to decode the value
    const decoded = decodeURIComponent(value)
    
    // If decoding succeeds and produces a different result, use it
    // If the value was already decoded, this will return the same value
    return decoded
  } catch (e) {
    // If decoding fails (e.g., value contains unencoded special characters),
    // the value is already in plain text format - return as-is
    log.debug('safeDecodeURIComponent - Value appears to be plain text, using as-is')
    return value
  }
}

/**
 * Generate attachment filename for search results
 * @param {string} type - Search type ('grep' or 'find')
 * @param {string} pattern - Search pattern
 * @returns {string} Safe filename
 */
export function generateAttachmentFilename(type, pattern) {
  const safePattern = pattern.replace(/[^a-zA-Z0-9]/g, '_')
  return `${type}_${safePattern}.txt`
}
