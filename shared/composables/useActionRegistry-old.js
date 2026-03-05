/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-22",
 *   "console_calls_found": 55,
 *   "console_calls_migrated": 55,
 *   "migration_rate": 100,
 *   "logger_namespace": "action:registry",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Action Links Registry
 * 
 * Sistema de registro e execução de ações JavaScript que podem ser invocadas
 * por links gerados pelo AgenteLab nas respostas do chat.
 * 
 * Formato de Action Link no Markdown:
 * [Texto do Link](action:action_name?param1=value1&param2=value2)
 * 
 * Exemplo:
 * [Criar Célula](action:create_cell?type=code&title=Minha%20Célula)
 * [Buscar Arquivos](action:grep?pattern=async%20def&path=backend)
 */

import { ref } from 'vue'
import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:registry')

// Registry de ações disponíveis
const actionRegistry = ref(new Map())

// ========================================
// OUTPUT STRATEGY CONFIGURATION
// ========================================

/**
 * Limits for intelligent output strategy
 */
const OUTPUT_STRATEGY_LIMITS = {
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
function shouldUseAttachment(content) {
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
function truncateIfNeeded(content, type) {
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
function formatGrepResults(data, pattern) {
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
function formatFindResults(data, pattern) {
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
function formatFileSize(bytes) {
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
function safeDecodeURIComponent(value) {
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
function generateAttachmentFilename(type, pattern) {
  const safePattern = pattern.replace(/[^a-zA-Z0-9]/g, '_')
  return `${type}_${safePattern}.txt`
}

// ========================================
// ACTION REGISTRY FUNCTIONS
// ========================================


/**
 * Registra uma nova ação
 * @param {string} name - Nome da ação (usado na URL action:name)
 * @param {Function} handler - Função handler(params, context)
 * @param {Object} metadata - Metadados da ação (descrição, parâmetros esperados)
 */
export function registerAction(name, handler, metadata = {}) {
  actionRegistry.value.set(name, {
    name,
    handler,
    metadata: {
      description: metadata.description || '',
      params: metadata.params || [],
      category: metadata.category || 'general',
      ...metadata
    }
  })
  
  log.debug(`Registered action: ${name}`)
}

/**
 * Remove uma ação do registry
 * @param {string} name - Nome da ação
 */
export function unregisterAction(name) {
  actionRegistry.value.delete(name)
  log.debug(`Unregistered action: ${name}`)
}

/**
 * Executa uma ação registrada
 * @param {string} name - Nome da ação
 * @param {Object} params - Parâmetros da ação
 * @param {Object} context - Contexto de execução (stores, router, etc)
 * @returns {Promise<any>} Resultado da execução
 */
export async function executeAction(name, params = {}, context = {}) {
  const action = actionRegistry.value.get(name)
  
  if (!action) {
    log.error(`Action not found: ${name}`)
    throw new Error(`Ação não encontrada: ${name}`)
  }
  
  log.debug(`Executing action: ${name}`, params)
  
  try {
    const result = await action.handler(params, context)
    log.debug(`Action completed: ${name}`, result)
    return result
  } catch (error) {
    log.error(`Action failed: ${name}`, error)
    throw error
  }
}

/**
 * Obtém a lista de ações registradas
 * @param {string} category - Filtrar por categoria (opcional)
 * @returns {Array} Lista de ações
 */
export function getRegisteredActions(category = null) {
  const actions = Array.from(actionRegistry.value.values())
  
  if (category) {
    return actions.filter(a => a.metadata.category === category)
  }
  
  return actions
}

/**
 * Verifica se uma ação está registrada
 * @param {string} name - Nome da ação
 * @returns {boolean}
 */
export function hasAction(name) {
  return actionRegistry.value.has(name)
}

/**
 * Obtém os metadados de uma ação
 * @param {string} name - Nome da ação
 * @returns {Object|null} Metadados da ação ou null se não encontrada
 */
export function getActionMetadata(name) {
  const action = actionRegistry.value.get(name)
  return action ? action.metadata : null
}

/**
 * Verifica se uma ação é do tipo POST/proposal
 * @param {string} name - Nome da ação
 * @returns {boolean} True se a ação é uma proposta (POST), false caso contrário
 */
export function isProposalAction(name) {
  const metadata = getActionMetadata(name)
  return metadata ? metadata.category === 'proposal' : false
}

/**
 * Parse de URL de ação
 * @param {string} url - URL no formato action:name?params
 * @returns {Object} {name, params}
 */
export function parseActionURL(url) {
  if (!url.startsWith('action:')) {
    throw new Error('URL inválida - deve começar com "action:"')
  }
  
  const withoutPrefix = url.substring(7) // Remove 'action:'
  const [name, queryString] = withoutPrefix.split('?')
  
  const params = {}
  if (queryString) {
    const urlParams = new URLSearchParams(queryString)
    for (const [key, value] of urlParams.entries()) {
      params[key] = value
    }
  }
  
  return { name, params }
}

/**
 * Cria uma URL de ação
 * @param {string} name - Nome da ação
 * @param {Object} params - Parâmetros da ação
 * @returns {string} URL formatada
 */
export function createActionURL(name, params = {}) {
  const queryParams = new URLSearchParams(params)
  const queryString = queryParams.toString()
  
  return `action:${name}${queryString ? '?' + queryString : ''}`
}

// ========================================
// AÇÕES BUILT-IN (Pré-registradas)
// ========================================

/**
 * Inicializa ações padrão do sistema
 * @param {Object} context - Contexto global (stores, router)
 */
export function initializeDefaultActions(context) {
  // Ação: Criar Célula
  registerAction(
    'create_cell',
    async (params, ctx) => {
      const { type = 'unclassified', title = '', content = '' } = params
      
      // Implementar criação de célula
      // Usar store ou serviço apropriado
      log.debug('Creating cell:', { type, title, content })
      
      // Exemplo: navegar para a célula criada
      if (ctx.router) {
        // ctx.router.push({ name: 'cell', params: { id: newCellId } })
      }
      
      return { success: true, message: 'Célula criada com sucesso' }
    },
    {
      description: 'Cria uma nova célula no notebook',
      params: [
        { name: 'type', type: 'string', required: false, default: 'unclassified' },
        { name: 'title', type: 'string', required: false },
        { name: 'content', type: 'string', required: false }
      ],
      category: 'cell'
    }
  )
  
    // Ação: Executar Grep
  registerAction(
    'grep',
    async (params, ctx) => {
      const { pattern, path = '.', file_pattern, case_sensitive = false, max_results = 100 } = params
      
      log.debug('grep - Execution started:', { pattern, path, file_pattern })
      
      if (!pattern) {
        throw new Error('Parâmetro "pattern" é obrigatório')
      }
      
      const chatStore = ctx.chatStore
      if (!chatStore) {
        throw new Error('ChatStore não disponível')
      }
      
      try {
        // Build query parameters
        const API_BASE = window.location.origin
        const url = new URL(`${API_BASE}/api/search/grep`)
        url.searchParams.append('pattern', pattern)
        url.searchParams.append('path', path)
        if (file_pattern) {
          url.searchParams.append('file_pattern', file_pattern)
        }
        url.searchParams.append('case_sensitive', case_sensitive.toString())
        url.searchParams.append('max_results', max_results.toString())
        
        log.debug('grep - Fetching from URL:', url.toString())
        
        // Fetch results from backend
        const response = await apiService.fetch(url.toString(), {
          headers: {
            'Content-Type': 'application/json',
          },
        })
        
        if (!response.ok) {
          let errorMessage = 'Erro ao executar busca'
          try {
            const errorData = await response.json()
            errorMessage = errorData.detail || errorMessage
          } catch (parseError) {
            errorMessage = `Erro HTTP ${response.status}: ${response.statusText}`
          }
          throw new Error(errorMessage)
        }
        
        const data = await response.json()
        
        log.debug('grep - Response data:', {
          status: data?.status,
          count: data?.count,
          hasMatches: !!(data?.matches),
          matchesLength: data?.matches?.length || 0
        })
        
        if (data && data.status === 'ok') {
          // Format results
          const formattedContent = formatGrepResults(data, pattern)
          
          // Apply intelligent truncation if needed
          const truncationResult = truncateIfNeeded(formattedContent, 'grep')
          const finalContent = truncationResult.content
          
          log.debug('grep - Formatted content:', {
            contentType: typeof finalContent,
            contentLength: finalContent.length,
            originalLength: truncationResult.originalSize,
            wasTruncated: truncationResult.wasTruncated,
            contentPreview: finalContent.substring(0, 100)
          })
          
          // Apply intelligent output strategy
          const shouldAttach = shouldUseAttachment(finalContent)
          
          log.debug('grep - Output strategy decision:', {
            shouldAttach,
            contentLength: finalContent.length,
            threshold: OUTPUT_STRATEGY_LIMITS.CHARS_THRESHOLD,
            wasTruncated: truncationResult.wasTruncated
          })
          
          if (shouldAttach) {
            // Attach as file for large results
            const filename = generateAttachmentFilename('grep', pattern)
            const success = chatStore.addAttachment(filename, finalContent, 'text')
            
            if (success) {
              log.debug('grep - Results attached to chat:', filename)
              return { 
                success: true, 
                message: `Busca concluída: ${data.count} resultados anexados${truncationResult.wasTruncated ? ' (truncado)' : ''}` 
              }
            } else {
              throw new Error('Não foi possível anexar os resultados ao chat')
            }
          } else {
            // Insert into input for small results
            log.debug('grep - Calling insertContentIntoInput with:', {
              payloadType: 'object',
              hasContent: true,
              contentLength: finalContent.length,
              wasTruncated: truncationResult.wasTruncated
            })
            
            chatStore.insertContentIntoInput({ content: finalContent })
            log.debug('grep - Results inserted into input')
            return { 
              success: true, 
              message: `Busca concluída: ${data.count} resultados` 
            }
          }
        } else {
          throw new Error('Resposta inválida do servidor')
        }
      } catch (error) {
        log.error('grep - Error:', error)
        
        // Format error message for user display
        let errorMessage = `❌ Erro ao executar grep:\n\n${error.message}`
        
        // Add helpful context based on error type
        if (error.message.includes('404') || error.message.includes('not found') || error.message.includes('Path not found')) {
          errorMessage += `\n\n💡 Dica: Verifique se o caminho "${path}" existe e está correto.`
        } else if (error.message.includes('400') || error.message.includes('Bad Request')) {
          errorMessage += `\n\n💡 Dica: Verifique os parâmetros da busca (pattern, path).`
        } else if (error.message.includes('500') || error.message.includes('Internal Server Error')) {
          errorMessage += `\n\n💡 Dica: Erro no servidor. Verifique os logs do backend.`
        } else if (error.message.includes('Network') || error.message.includes('fetch')) {
          errorMessage += `\n\n💡 Dica: Verifique se o backend está rodando.`
        }
        
        // Display error in chat input
        try {
          chatStore.insertContentIntoInput({ content: errorMessage })
          log.debug('grep - Error message displayed in chat')
        } catch (displayError) {
          log.error('grep - Failed to display error in chat:', displayError)
        }
        
        // Re-throw to maintain error propagation
        throw error
      }
    },
    {
      description: 'Busca padrões de texto em arquivos (suporta regex e wildcards no path)',
      params: [
        { name: 'pattern', type: 'string', required: true, description: 'Padrão de busca (regex detectado automaticamente, ex: "foo|bar", "^import")' },
        { name: 'path', type: 'string', required: false, default: '.', description: 'Caminho para buscar (suporta wildcards: *, ?, [], ex: "backend/*/routers")' },
        { name: 'file_pattern', type: 'string', required: false, description: 'Filtro de arquivo (ex: "*.py")' },
        { name: 'case_sensitive', type: 'boolean', required: false, default: false },
        { name: 'max_results', type: 'number', required: false, default: 100 }
      ],
      category: 'runtime'
    }
  )
  
  // Ação: Buscar Arquivos
  registerAction(
    'find',
    async (params, ctx) => {
      const { pattern = '*', path = '.', recursive = true } = params
      
      // Pattern defaults to '*' (all files) if not provided
      // This allows searching with just path wildcards
      
      const chatStore = ctx.chatStore
      if (!chatStore) {
        throw new Error('ChatStore não disponível')
      }
      
      try {
        // Build query parameters
        const API_BASE = window.location.origin
        const url = new URL(`${API_BASE}/api/search/find`)
        url.searchParams.append('pattern', pattern)
        url.searchParams.append('path', path)
        url.searchParams.append('recursive', recursive.toString())
        
        log.debug('find - Fetching from URL:', url.toString())
        
        // Fetch results from backend
        const response = await apiService.fetch(url.toString(), {
          headers: {
            'Content-Type': 'application/json',
          },
        })
        
        if (!response.ok) {
          let errorMessage = 'Erro ao buscar arquivos'
          try {
            const errorData = await response.json()
            errorMessage = errorData.detail || errorMessage
          } catch (parseError) {
            errorMessage = `Erro HTTP ${response.status}: ${response.statusText}`
          }
          throw new Error(errorMessage)
        }
        
        const data = await response.json()
        
        log.debug('find - Response data:', {
          status: data?.status,
          count: data?.count,
          hasMatches: !!(data?.matches),
          matchesLength: data?.matches?.length || 0
        })
        
        if (data && data.status === 'ok') {
          // Format results
          const formattedContent = formatFindResults(data, pattern)
          
          // Apply intelligent truncation if needed
          const truncationResult = truncateIfNeeded(formattedContent, 'find')
          const finalContent = truncationResult.content
          
          log.debug('find - Formatted content:', {
            contentType: typeof finalContent,
            contentLength: finalContent.length,
            originalLength: truncationResult.originalSize,
            wasTruncated: truncationResult.wasTruncated,
            contentPreview: finalContent.substring(0, 100)
          })
          
          // Apply intelligent output strategy
          const shouldAttach = shouldUseAttachment(finalContent)
          
          log.debug('find - Output strategy decision:', {
            shouldAttach,
            contentLength: finalContent.length,
            threshold: OUTPUT_STRATEGY_LIMITS.CHARS_THRESHOLD,
            wasTruncated: truncationResult.wasTruncated
          })
          
          if (shouldAttach) {
            // Attach as file for large results
            const filename = generateAttachmentFilename('find', pattern)
            const success = chatStore.addAttachment(filename, finalContent, 'text')
            
            if (success) {
              log.debug('find - Results attached to chat:', filename)
              return { 
                success: true, 
                message: `Busca concluída: ${data.count} arquivos anexados${truncationResult.wasTruncated ? ' (truncado)' : ''}` 
              }
            } else {
              throw new Error('Não foi possível anexar os resultados ao chat')
            }
          } else {
            // Insert into input for small results
            log.debug('find - Calling insertContentIntoInput with:', {
              payloadType: 'object',
              hasContent: true,
              contentLength: finalContent.length,
              wasTruncated: truncationResult.wasTruncated
            })
            
            chatStore.insertContentIntoInput({ content: finalContent })
            log.debug('find - Results inserted into input')
            return { 
              success: true, 
              message: `Busca concluída: ${data.count} arquivos` 
            }
          }
        } else {
          throw new Error('Resposta inválida do servidor')
        }
      } catch (error) {
        log.error('find - Error:', error)
        
        // Format error message for user display
        let errorMessage = `❌ Erro ao executar find:\n\n${error.message}`
        
        // Add helpful context based on error type
        if (error.message.includes('404') || error.message.includes('not found') || error.message.includes('Path not found')) {
          errorMessage += `\n\n💡 Dica: Verifique se o caminho "${path}" existe e está correto.`
        } else if (error.message.includes('400') || error.message.includes('Bad Request')) {
          errorMessage += `\n\n💡 Dica: Verifique os parâmetros da busca (pattern, path).`
        } else if (error.message.includes('500') || error.message.includes('Internal Server Error')) {
          errorMessage += `\n\n💡 Dica: Erro no servidor. Verifique os logs do backend.`
        } else if (error.message.includes('Network') || error.message.includes('fetch')) {
          errorMessage += `\n\n💡 Dica: Verifique se o backend está rodando.`
        }
        
        // Display error in chat input
        try {
          chatStore.insertContentIntoInput({ content: errorMessage })
          log.debug('find - Error message displayed in chat')
        } catch (displayError) {
          log.error('find - Failed to display error in chat:', displayError)
        }
        
        // Re-throw to maintain error propagation
        throw error
      }
    },
    {
      description: 'Busca arquivos por padrão de nome (pattern padrão: "*", suporta wildcards no path)',
      params: [
        { name: 'pattern', type: 'string', required: false, default: '*', description: 'Padrão do nome do arquivo (glob, ex: "*.py", padrão: "*")' },
        { name: 'path', type: 'string', required: false, default: '.', description: 'Caminho inicial (suporta wildcards: *, ?, [], ex: "src/*/components")' },
        { name: 'recursive', type: 'boolean', required: false, default: true }
      ],
      category: 'runtime'
    }
  )
  
  // Ação: Ler Arquivo
  registerAction(
    'read_file',
    async (params, ctx) => {
      const { path, paths, line_numbers = false } = params
      
      // Determine if single or multiple files
      let filePaths = []
      if (paths) {
        // Multiple files mode
        filePaths = paths.split(',').map(p => p.trim()).filter(p => p)
      } else if (path) {
        // Single file mode
        filePaths = [path]
      } else {
        throw new Error('Parâmetro "path" ou "paths" é obrigatório')
      }
      
      log.debug('read_file - Fetching files:', filePaths)
      
      const chatStore = ctx.chatStore
      if (!chatStore) {
        throw new Error('ChatStore não disponível')
      }
      
      try {
        // Fetch file(s) content using the API endpoint
        const API_BASE = window.location.origin
        const url = new URL(`${API_BASE}/api/files/load`)
        
        // Use new paths parameter for multi-file or single file
        if (paths || filePaths.length > 1) {
          url.searchParams.append('paths', filePaths.join(','))
        } else {
          // Legacy single file mode (for backward compatibility)
          const pathParts = filePaths[0].split('/')
          const filename = pathParts[pathParts.length - 1]
          const folder = pathParts.slice(0, -1).join('/')
          url.searchParams.append('filename', filename)
          if (folder) {
            url.searchParams.append('folder', folder)
          }
        }
        
        // Add line_numbers parameter if requested
        if (line_numbers) {
          url.searchParams.append('line_numbers', 'true')
        }
        
        log.debug('read_file - Fetching from URL:', url.toString())
        
        const response = await apiService.fetch(url.toString(), {
          headers: {
            'Content-Type': 'application/json',
          },
        })
        
        if (!response.ok) {
          let errorMessage = 'Erro ao carregar arquivo'
          try {
            const errorData = await response.json()
            errorMessage = errorData.details || errorMessage
          } catch (parseError) {
            errorMessage = `Erro HTTP ${response.status}: ${response.statusText}`
          }
          throw new Error(errorMessage)
        }
        
        const data = await response.json()
        
        // Handle both single file and multi-file responses
        if (data && data.status === 'ok') {
          if (data.files) {
            // Multi-file response
            let successCount = 0
            for (const file of data.files) {
              const filename = file.path.split('/').pop()
              const success = chatStore.addAttachment(filename, file.content, 'text', file.path)
              if (success) {
                successCount++
              }
            }
            
            log.debug(`read_file - ${successCount} files attached to chat`)
            return { 
              success: true, 
              message: `${successCount} arquivo(s) anexado(s) ao chat com sucesso` 
            }
          } else if (data.content !== undefined) {
            // Single file response (legacy)
            const filename = filePaths[0].split('/').pop()
            const success = chatStore.addAttachment(filename, data.content, 'text', filePaths[0])
            
            if (success) {
              log.debug('read_file - File content attached to chat:', filename)
              return { 
                success: true, 
                message: `Arquivo "${filename}" anexado ao chat com sucesso` 
              }
            } else {
              throw new Error('Não foi possível anexar o arquivo ao chat')
            }
          } else {
            throw new Error('Resposta inválida do servidor: nenhum conteúdo retornado')
          }
        } else {
          const actualStatus = data?.status || 'undefined'
          throw new Error(`Resposta inválida do servidor: status="${actualStatus}"`)
        }
      } catch (error) {
        log.error('read_file - Error:', error)
        throw error
      }
    },
    {
      description: 'Lê o conteúdo de um ou mais arquivos e anexa ao chat',
      params: [
        { name: 'path', type: 'string', required: false, description: 'Caminho para um único arquivo' },
        { name: 'paths', type: 'string', required: false, description: 'Caminhos separados por vírgula para múltiplos arquivos' },
        { name: 'line_numbers', type: 'boolean', required: false, default: false, description: 'Incluir números de linha no conteúdo' }
      ],
      category: 'runtime'
    }
  )
  
  // Ação: Propor Atualização de Arquivo
  registerAction(
    'propose_file_update',
    async (params, ctx) => {
      const { 
        path, 
        original_content, 
        new_content, 
        start_line, 
        end_line, 
        context_lines = 3,
        description = '' 
      } = params
      
      // Enhanced logging: Parameters received
      log.debug('propose_file_update - Parameters received:', {
        path,
        hasOriginalContent: !!original_content,
        originalContentLength: original_content?.length || 0,
        hasNewContent: !!new_content,
        newContentLength: new_content?.length || 0,
        startLine: start_line,
        endLine: end_line,
        contextLines: context_lines,
        description,
        mode: (start_line !== undefined && end_line !== undefined) ? 'snippet' : 'full-file'
      })
      
      if (!path) {
        throw new Error('Parâmetro "path" é obrigatório')
      }
      
      // Allow empty new_content for snippet deletions (snippet mode + empty = delete lines)
      // For non-snippet mode, new_content is required
      const is_snippet_mode = start_line !== undefined && end_line !== undefined
      if (new_content === undefined && !is_snippet_mode) {
        throw new Error('Parâmetro "new_content" é obrigatório')
      }
      
      log.debug('propose_file_update - Opening proposal for:', path)
      
      const chatStore = ctx.chatStore
      
      // Enhanced logging: ChatStore validation
      log.debug('propose_file_update - ChatStore state:', {
        hasChatStore: !!chatStore,
        chatStoreType: typeof chatStore,
        hasShowFileProposal: !!(chatStore && typeof chatStore.showFileProposal === 'function')
      })
      
      if (!chatStore) {
        throw new Error('ChatStore não disponível')
      }
      
      try {
        let finalOriginalContent = original_content
        let finalDescription = description
        
        // Enhanced logging: Mode detection
        log.debug('propose_file_update - Mode detection:', {
          hasStartLine: start_line !== undefined,
          hasEndLine: end_line !== undefined,
          hasOriginalContent: !!original_content,
          selectedMode: (start_line !== undefined && end_line !== undefined) ? 'SNIPPET' : 'FULL-FILE'
        })
        
        // If start_line and end_line are provided, fetch the snippet from backend
        if (start_line !== undefined && end_line !== undefined) {
          log.debug(`propose_file_update - Snippet mode: lines ${start_line}-${end_line}`)
          
          const API_BASE = window.location.origin
          const snippetUrl = `${API_BASE}/api/files/snippet`
          
          // Prepare request body
          const requestBody = {
            path: path,
            start_line: start_line,
            end_line: end_line,
            context_lines: context_lines
          }
          
          // Enhanced logging: API request details
          log.debug('propose_file_update - Building API request:', {
            apiBase: API_BASE,
            endpoint: '/api/files/snippet',
            method: 'POST',
            body: requestBody
          })
          
          // Enhanced logging: API request sent
          log.debug('propose_file_update - API request sent:', {
            url: snippetUrl,
            method: 'POST',
            timestamp: new Date().toISOString()
          })
          
          const response = await apiService.fetch(snippetUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
          })
          
          // Enhanced logging: API response received
          log.debug('propose_file_update - API response received:', {
            status: response.status,
            statusText: response.statusText,
            ok: response.ok,
            contentType: response.headers.get('content-type'),
            timestamp: new Date().toISOString()
          })
          
          if (!response.ok) {
            log.error('propose_file_update - API error response:', {
              status: response.status,
              statusText: response.statusText,
              url: snippetUrl
            })
            
            let errorMessage = 'Erro ao carregar snippet do arquivo'
            let errorDetails = null
            
            try {
              const errorData = await response.json()
              errorDetails = errorData
              errorMessage = errorData.details || errorMessage
              
              log.error('propose_file_update - Error details:', {
                errorData,
                extractedMessage: errorMessage
              })
            } catch (parseError) {
              errorMessage = `Erro HTTP ${response.status}: ${response.statusText}`
              log.error('propose_file_update - Failed to parse error response:', parseError)
            }
            throw new Error(errorMessage)
          }
          
          // Enhanced logging: Parsing response
          log.debug('propose_file_update - Parsing response...')
          
          const snippetData = await response.json()
          
          // Enhanced logging: Response parsed
          log.debug('propose_file_update - Response parsed:', {
            status: snippetData?.status,
            hasContent: !!snippetData?.content,
            contentLength: snippetData?.content?.length || 0,
            path: snippetData?.path,
            startLine: snippetData?.start_line,
            endLine: snippetData?.end_line,
            actualStart: snippetData?.actual_start,
            actualEnd: snippetData?.actual_end,
            lines: snippetData?.lines,
            totalFileLines: snippetData?.total_file_lines,
            contextLines: snippetData?.context_lines
          })
          
          if (snippetData && snippetData.status === 'ok') {
            finalOriginalContent = snippetData.content
            
            // Enhance description with line number info
            const lineInfo = `Linhas ${snippetData.actual_start}-${snippetData.actual_end}`
            finalDescription = description 
              ? `${lineInfo}: ${description}` 
              : lineInfo
            
            // Enhanced logging: Snippet validation successful
            log.debug('propose_file_update - Snippet validation successful:', {
              originalContentLength: finalOriginalContent.length,
              lineInfo,
              finalDescription,
              actualRange: `${snippetData.actual_start}-${snippetData.actual_end}`,
              requestedRange: `${start_line}-${end_line}`,
              contextApplied: snippetData.actual_start < start_line || snippetData.actual_end > end_line
            })
          } else {
            log.error('propose_file_update - Invalid snippet response:', {
              hasSnippetData: !!snippetData,
              status: snippetData?.status,
              expectedStatus: 'ok'
            })
            throw new Error('Resposta inválida ao carregar snippet')
          }
        } else if (!original_content) {
          // Neither snippet mode nor full content mode - error
          throw new Error('Parâmetro "original_content" ou "start_line"/"end_line" são obrigatórios')
        }
        
        // Enhanced logging: Final proposal data
        log.debug('propose_file_update - Preparing to show file proposal:', {
          type: 'update',
          filePath: path,
          hasOriginalContent: !!finalOriginalContent,
          originalContentLength: finalOriginalContent?.length || 0,
          hasNewContent: !!new_content,
          newContentLength: new_content?.length || 0,
          description: finalDescription,
          startLine: start_line,
          endLine: end_line
        })
        
        // Show file proposal modal
        // Note: Use safeDecodeURIComponent to handle both encoded and plain text parameters
        // Parameters from JSON action payloads are NOT URI-encoded and should be used as-is
        chatStore.showFileProposal({
          type: 'update',
          filePath: path,
          originalContent: finalOriginalContent ? safeDecodeURIComponent(finalOriginalContent) : '',
          content: safeDecodeURIComponent(new_content),
          description: finalDescription ? safeDecodeURIComponent(finalDescription) : '',
          startLine: start_line,
          endLine: end_line
        })
        
        log.debug('propose_file_update - File proposal shown successfully')
        
        return { 
          success: true, 
          message: `Proposta de atualização aberta para: ${path}` 
        }
      } catch (error) {
        log.error('propose_file_update - Error:', {
          errorMessage: error.message,
          errorStack: error.stack,
          errorName: error.name
        })
        throw error
      }
    },
    {
      description: 'Propõe uma atualização de arquivo existente com diff visual (suporta snippets)',
      params: [
        { name: 'path', type: 'string', required: true },
        { name: 'original_content', type: 'string', required: false, description: 'Conteúdo original (modo full-file)' },
        { name: 'new_content', type: 'string', required: true },
        { name: 'start_line', type: 'number', required: false, description: 'Linha inicial (modo snippet)' },
        { name: 'end_line', type: 'number', required: false, description: 'Linha final (modo snippet)' },
        { name: 'context_lines', type: 'number', required: false, default: 3, description: 'Linhas de contexto antes/depois' },
        { name: 'description', type: 'string', required: false }
      ],
      category: 'proposal'
    }
  )
  
  // Ação: Propor Criação de Arquivo
  registerAction(
    'propose_file_creation',
    async (params, ctx) => {
      const { path, content, description = '' } = params
      
      if (!path) {
        throw new Error('Parâmetro "path" é obrigatório')
      }
      if (!content) {
        throw new Error('Parâmetro "content" é obrigatório')
      }
      
      log.debug('propose_file_creation - Opening proposal for:', path)
      
      const chatStore = ctx.chatStore
      if (!chatStore) {
        throw new Error('ChatStore não disponível')
      }
      
      // Show file proposal modal
      // Note: Use safeDecodeURIComponent to handle both encoded and plain text parameters
      chatStore.showFileProposal({
        type: 'create',
        filePath: path,
        content: safeDecodeURIComponent(content),
        description: safeDecodeURIComponent(description)
      })
      
      return { 
        success: true, 
        message: `Proposta de criação aberta para: ${path}` 
      }
    },
    {
      description: 'Propõe a criação de um novo arquivo',
      params: [
        { name: 'path', type: 'string', required: true },
        { name: 'content', type: 'string', required: true },
        { name: 'description', type: 'string', required: false }
      ],
      category: 'proposal'
    }
  )
  
  // Ação: Abrir Documentação
  registerAction(
    'open_docs',
    async (params, ctx) => {
      const { path } = params
      
      if (!path) {
        throw new Error('Parâmetro "path" é obrigatório')
      }
      
      // Abrir documentação em nova aba ou modal
      window.open(path, '_blank')
      
      return { success: true, message: 'Documentação aberta' }
    },
    {
      description: 'Abre documentação em nova aba',
      params: [
        { name: 'path', type: 'string', required: true }
      ],
      category: 'navigation'
    }
  )
  
  // Ação: Copiar para Clipboard
  registerAction(
    'copy_to_clipboard',
    async (params, ctx) => {
      const { text } = params
      
      if (!text) {
        throw new Error('Parâmetro "text" é obrigatório')
      }
      
      await navigator.clipboard.writeText(text)
      
      return { success: true, message: 'Texto copiado!' }
    },
    {
      description: 'Copia texto para a área de transferência',
      params: [
        { name: 'text', type: 'string', required: true }
      ],
      category: 'utility'
    }
  )
  
  // Note: navigate action is disabled because this app doesn't use vue-router
  // Keeping it registered for protocol completeness, but marked as unavailable
  registerAction(
    'navigate',
    async (params, ctx) => {
      const { route } = params
      
      if (!route) {
        throw new Error('Parâmetro "route" é obrigatório')
      }
      
      log.warn('Navigate action is not available (app does not use vue-router)')
      throw new Error('Navegação não suportada nesta aplicação - o app não usa vue-router')
    },
    {
      description: 'Navega para uma rota da aplicação (NÃO DISPONÍVEL - app sem router)',
      params: [
        { name: 'route', type: 'string', required: true }
      ],
      category: 'navigation',
      available: false // Mark as unavailable
    }
  )
  
  // ========================================
  // DISCOVER_ACTIONS: Meta-action for LLM discovery
  // ========================================
  registerAction(
    'discover_actions',
    async (params, ctx) => {
      const { mode, filter_label, filter_action } = params
      
      log.info('[DISCOVER_ACTIONS] Discovery request', { mode, filter_label, filter_action })
      
      if (!mode) {
        throw new Error('Parâmetro "mode" é obrigatório (list_all, by_label, action_details)')
      }
      
      // Import discovery composable dynamically to avoid circular dependencies
      const { useActionDiscovery } = await import('@/composables/useActionDiscovery')
      const discovery = useActionDiscovery()
      
      try {
        let result
        let formattedOutput
        
        switch (mode) {
          case 'list_all': {
            // List all labels and actions
            result = await discovery.discoverAll()
            
            // Format for display
            formattedOutput = '🔍 **Available Action Categories:**\n\n'
            const sortedLabels = Object.keys(result).sort()
            
            sortedLabels.forEach(labelKey => {
              const actions = result[labelKey]
              formattedOutput += `**${labelKey}** (${actions.length} actions):\n`
              actions.forEach(actionName => {
                formattedOutput += `  • ${actionName}\n`
              })
              formattedOutput += '\n'
            })
            
            formattedOutput += `\n📊 Total: ${sortedLabels.length} categories, ${
              Object.values(result).flat().length
            } actions`
            
            break
          }
          
          case 'by_label': {
            // Get actions by label
            if (!filter_label) {
              throw new Error('Parâmetro "filter_label" é obrigatório para mode="by_label"')
            }
            
            result = await discovery.discoverByLabel(filter_label)
            
            if (result.length === 0) {
              formattedOutput = `⚠️ No actions found for label: "${filter_label}"`
            } else {
              formattedOutput = `🏷️ **Actions for label "${filter_label}":**\n\n`
              
              result.forEach(action => {
                formattedOutput += `**${action.name}**\n`
                formattedOutput += `  ${action.description.split('\n')[0]}\n`
                
                if (action.parameters && action.parameters.length > 0) {
                  formattedOutput += '  Parameters:\n'
                  action.parameters.forEach(param => {
                    const req = param.required ? '(required)' : '(optional)'
                    formattedOutput += `    • ${param.name}: ${param.type} ${req}\n`
                  })
                }
                
                if (action.labels && action.labels.length > 1) {
                  formattedOutput += `  Labels: ${action.labels.join(', ')}\n`
                }
                
                formattedOutput += '\n'
              })
              
              formattedOutput += `📊 Found ${result.length} action(s)`
            }
            
            break
          }
          
          case 'action_details': {
            // Get specific action details
            if (!filter_label || !filter_action) {
              throw new Error(
                'Parâmetros "filter_label" e "filter_action" são obrigatórios para mode="action_details"'
              )
            }
            
            result = await discovery.discoverAction(filter_label, filter_action)
            
            if (!result) {
              formattedOutput = `⚠️ Action "${filter_action}" not found in label "${filter_label}"`
            } else {
              formattedOutput = `📋 **Action Details: ${result.name}**\n\n`
              
              // Description
              formattedOutput += `**Description:**\n${result.description}\n\n`
              
              // Parameters
              if (result.parameters && result.parameters.length > 0) {
                formattedOutput += '**Parameters:**\n'
                result.parameters.forEach(param => {
                  const req = param.required ? '✓ Required' : '○ Optional'
                  formattedOutput += `  ${req} **${param.name}** (${param.type})\n`
                  if (param.description) {
                    formattedOutput += `    ${param.description}\n`
                  }
                  if (param.default !== null && param.default !== undefined) {
                    formattedOutput += `    Default: ${JSON.stringify(param.default)}\n`
                  }
                })
                formattedOutput += '\n'
              }
              
              // Metadata
              if (result.metadata) {
                formattedOutput += '**Metadata:**\n'
                formattedOutput += `  Version: ${result.metadata.version}\n`
                formattedOutput += `  Type: ${result.metadata.action_type}\n`
                formattedOutput += `  Status: ${result.metadata.status}\n`
                formattedOutput += `  Labels: ${result.metadata.labels.join(', ')}\n\n`
              }
              
              // Examples
              if (result.examples && result.examples.length > 0) {
                formattedOutput += '**Examples:**\n'
                result.examples.forEach((example, idx) => {
                  formattedOutput += `  ${idx + 1}. ${example.name || 'Example'}\n`
                  if (example.description) {
                    formattedOutput += `     ${example.description}\n`
                  }
                })
                formattedOutput += '\n'
              }
              
              // Best Practices
              if (result.best_practices && result.best_practices.length > 0) {
                formattedOutput += '**Best Practices:**\n'
                result.best_practices.forEach(practice => {
                  formattedOutput += `  ✓ ${practice}\n`
                })
                formattedOutput += '\n'
              }
              
              // Tips
              if (result.tips && result.tips.length > 0) {
                formattedOutput += '**Tips:**\n'
                result.tips.forEach(tip => {
                  formattedOutput += `  💡 ${tip}\n`
                })
              }
            }
            
            break
          }
          
          default:
            throw new Error(`Modo inválido: "${mode}". Use: list_all, by_label, ou action_details`)
        }
        
        log.success('[DISCOVER_ACTIONS] Discovery completed', { mode, resultSize: result?.length || 0 })
        
        // Apply intelligent output feedback strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Check output size to determine feedback method
          if (formattedOutput.length < 5000) {
            // Prompt-based feedback for concise results
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('[DISCOVER_ACTIONS] Results inserted into input')
          } else {
            // Attachment-based feedback for larger results
            const filename = `action_discovery_${mode}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('[DISCOVER_ACTIONS] Results attached to chat:', filename)
          }
        }
        
        // Return both the raw result and formatted output
        return {
          success: true,
          mode,
          filter_label,
          filter_action,
          data: result,
          formatted: formattedOutput,
          message: formattedOutput
        }
        
      } catch (error) {
        log.error('[DISCOVER_ACTIONS] Discovery failed', { error: error.message })
        throw error
      }
    },
    {
      description: 'Descobre ações disponíveis no sistema (meta-ação para LLM)',
      params: [
        { 
          name: 'mode', 
          type: 'string', 
          required: true,
          description: 'Modo de descoberta: list_all, by_label, action_details'
        },
        { 
          name: 'filter_label', 
          type: 'string', 
          required: false,
          description: 'Label para filtrar (obrigatório para by_label e action_details)'
        },
        { 
          name: 'filter_action', 
          type: 'string', 
          required: false,
          description: 'Nome da ação específica (obrigatório para action_details)'
        }
      ],
      category: 'discovery',
      available: true
    }
  )
  
  // ========================================
  // GITHUB PR ACTIONS: Backend-only actions
  // ========================================
  
  // Action: Get PR Report
  registerAction(
    'get_pr_report',
    async (params, ctx) => {
      const { owner, repo, pr_number } = params
      
      if (!owner || !repo || !pr_number) {
        throw new Error('Parâmetros obrigatórios: owner, repo, pr_number')
      }
      
      log.debug('get_pr_report - Fetching PR report:', { owner, repo, pr_number })
      
      try {
        const response = await apiService.fetch(
          `/api/github/pr/report?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&pr_number=${pr_number}`
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the report for display
        const formattedReport = `
📊 **Pull Request #${data.number}**

**Title:** ${data.title}

**State:** ${data.state} ${data.merged ? '(Merged ✓)' : ''}
**Author:** ${data.user}
**Base Branch:** ${data.base_branch}
**Head Branch:** ${data.head_branch}

**Statistics:**
- Commits: ${data.commits_count}
- Files Changed: ${data.changed_files}
- Additions: +${data.additions}
- Deletions: -${data.deletions}

**Timestamps:**
- Created: ${data.created_at || 'N/A'}
- Updated: ${data.updated_at || 'N/A'}
${data.merged_at ? `- Merged: ${data.merged_at}` : ''}

**URL:** ${data.url}

${data.body ? `\n**Description:**\n${data.body}` : ''}
`.trim()
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedReport })
        }
        
        log.success('get_pr_report - Report fetched successfully')
        return { success: true, data, message: 'PR report fetched successfully' }
      } catch (error) {
        log.error('get_pr_report - Error:', error)
        throw new Error(`Failed to fetch PR report: ${error.message}`)
      }
    },
    {
      description: 'Get Pull Request report with metadata and statistics',
      params: [
        { name: 'owner', type: 'string', required: true },
        { name: 'repo', type: 'string', required: true },
        { name: 'pr_number', type: 'integer', required: true }
      ],
      category: 'github',
      available: true
    }
  )
  
  // Action: Get PR Changes
  registerAction(
    'get_pr_changes',
    async (params, ctx) => {
      const { owner, repo, pr_number } = params
      
      if (!owner || !repo || !pr_number) {
        throw new Error('Parâmetros obrigatórios: owner, repo, pr_number')
      }
      
      log.debug('get_pr_changes - Fetching PR changes:', { owner, repo, pr_number })
      
      try {
        const response = await apiService.fetch(
          `/api/github/pr/changes?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&pr_number=${pr_number}`
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the changes list for display
        let formattedChanges = `📝 **Changed Files in PR #${pr_number}** (${data.total} files)\n\n`
        
        data.changes.forEach(change => {
          const statusIcon = {
            'added': '✨',
            'modified': '📝',
            'removed': '🗑️',
            'renamed': '🔄'
          }[change.status] || '📄'
          
          formattedChanges += `${statusIcon} **${change.filename}** (${change.status})\n`
          formattedChanges += `   +${change.additions} -${change.deletions} (~${change.changes} changes)\n`
          if (change.previous_filename) {
            formattedChanges += `   Renamed from: ${change.previous_filename}\n`
          }
          formattedChanges += '\n'
        })
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedChanges.length > 5000) {
            // For large outputs, attach as file
            const filename = `pr_${pr_number}_changes.txt`
            chatStore.addAttachment(filename, formattedChanges, 'text')
            log.debug('get_pr_changes - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedChanges })
          }
        }
        
        log.success('get_pr_changes - Changes fetched successfully:', { count: data.total })
        return { success: true, data, message: `Retrieved ${data.total} changed files` }
      } catch (error) {
        log.error('get_pr_changes - Error:', error)
        throw new Error(`Failed to fetch PR changes: ${error.message}`)
      }
    },
    {
      description: 'Get list of all changed files in a Pull Request',
      params: [
        { name: 'owner', type: 'string', required: true },
        { name: 'repo', type: 'string', required: true },
        { name: 'pr_number', type: 'integer', required: true }
      ],
      category: 'github',
      available: true
    }
  )
  
  // Action: Get PR File Diff
  registerAction(
    'get_pr_file_diff',
    async (params, ctx) => {
      const { owner, repo, pr_number, file_path } = params
      
      if (!owner || !repo || !pr_number || !file_path) {
        throw new Error('Parâmetros obrigatórios: owner, repo, pr_number, file_path')
      }
      
      log.debug('get_pr_file_diff - Fetching file diff:', { owner, repo, pr_number, file_path })
      
      try {
        const response = await apiService.fetch(
          `/api/github/pr/file-diff?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&pr_number=${pr_number}&file_path=${encodeURIComponent(file_path)}`
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the diff for display
        let formattedDiff = `📄 **File Diff: ${data.filename}**\n\n`
        formattedDiff += `**Status:** ${data.status}\n`
        formattedDiff += `**Changes:** +${data.additions} -${data.deletions} (~${data.changes} total)\n`
        if (data.previous_filename) {
          formattedDiff += `**Renamed from:** ${data.previous_filename}\n`
        }
        formattedDiff += '\n---\n\n'
        
        if (data.patch) {
          formattedDiff += '```diff\n'
          formattedDiff += data.patch
          formattedDiff += '\n```'
        } else {
          formattedDiff += '*(No diff available - file may be binary or too large)*'
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedDiff.length > 10000) {
            // For large diffs, attach as file
            const filename = `${file_path.replace(/\//g, '_')}_diff.txt`
            chatStore.addAttachment(filename, formattedDiff, 'text')
            log.debug('get_pr_file_diff - Diff attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedDiff })
          }
        }
        
        log.success('get_pr_file_diff - Diff fetched successfully')
        return { success: true, data, message: 'File diff retrieved successfully' }
      } catch (error) {
        log.error('get_pr_file_diff - Error:', error)
        throw new Error(`Failed to fetch file diff: ${error.message}`)
      }
    },
    {
      description: 'Get diff for a specific file in a Pull Request',
      params: [
        { name: 'owner', type: 'string', required: true },
        { name: 'repo', type: 'string', required: true },
        { name: 'pr_number', type: 'integer', required: true },
        { name: 'file_path', type: 'string', required: true }
      ],
      category: 'github',
      available: true
    }
  )
  
  // Action: Get PR New File Content
  registerAction(
    'get_pr_new_file_content',
    async (params, ctx) => {
      const { owner, repo, pr_number, file_path } = params
      
      if (!owner || !repo || !pr_number || !file_path) {
        throw new Error('Parâmetros obrigatórios: owner, repo, pr_number, file_path')
      }
      
      log.debug('get_pr_new_file_content - Fetching new file content:', { owner, repo, pr_number, file_path })
      
      try {
        const response = await apiService.fetch(
          `/api/github/pr/new-file-content?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&pr_number=${pr_number}&file_path=${encodeURIComponent(file_path)}`
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        if (data.error) {
          throw new Error(data.error)
        }
        
        // Format the file content for display
        let formattedContent = `📄 **New File: ${data.filename}**\n\n`
        formattedContent += `**Encoding:** ${data.encoding}\n`
        formattedContent += `**Size:** ${data.size ? formatFileSize(data.size) : 'Unknown'}\n`
        formattedContent += '\n---\n\n'
        
        if (data.content) {
          // Detect language from file extension for syntax highlighting
          const ext = data.filename.split('.').pop()
          const langMap = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'jsx': 'jsx',
            'tsx': 'tsx',
            'json': 'json',
            'yml': 'yaml',
            'yaml': 'yaml',
            'md': 'markdown',
            'html': 'html',
            'css': 'css',
            'sh': 'bash'
          }
          const lang = langMap[ext] || ext
          
          formattedContent += '```' + lang + '\n'
          formattedContent += data.content
          formattedContent += '\n```'
        } else {
          formattedContent += '*(No content available)*'
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedContent.length > 10000) {
            // For large files, attach as file
            const filename = data.filename.split('/').pop()
            chatStore.addAttachment(filename, data.content, 'text')
            log.debug('get_pr_new_file_content - Content attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedContent })
          }
        }
        
        log.success('get_pr_new_file_content - Content fetched successfully')
        return { success: true, data, message: 'New file content retrieved successfully' }
      } catch (error) {
        log.error('get_pr_new_file_content - Error:', error)
        throw new Error(`Failed to fetch new file content: ${error.message}`)
      }
    },
    {
      description: 'Get content of a newly added file in a Pull Request',
      params: [
        { name: 'owner', type: 'string', required: true },
        { name: 'repo', type: 'string', required: true },
        { name: 'pr_number', type: 'integer', required: true },
        { name: 'file_path', type: 'string', required: true }
      ],
      category: 'github',
      available: true
    }
  )
  
  // ========================================
  // CELLS ACTIONS: Backend-only RBAC actions
  // ========================================
  
  // Action: List Cells
  registerAction(
    'list_cells',
    async (params, ctx) => {
      const { assignee_id } = params
      
      log.debug('list_cells - Fetching cells list:', { assignee_id })
      
      try {
        const queryParams = assignee_id ? `?assignee_id=${encodeURIComponent(assignee_id)}` : ''
        const response = await apiService.fetch(`/api/cells/list${queryParams}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the cells list for display
        let formattedOutput = `📋 **Cells List** (${data.length} cell${data.length !== 1 ? 's' : ''})\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No cells found*'
        } else {
          // Group by status
          const byStatus = {}
          data.forEach(cell => {
            const status = cell.status || 'unknown'
            if (!byStatus[status]) byStatus[status] = []
            byStatus[status].push(cell)
          })
          
          // Display by status groups
          Object.entries(byStatus).forEach(([status, cells]) => {
            const statusIcon = {
              'pending': '⏳',
              'running': '🔄',
              'completed': '✅',
              'error': '❌'
            }[status] || '❓'
            
            formattedOutput += `**${statusIcon} ${status.toUpperCase()}** (${cells.length})\n`
            cells.forEach(cell => {
              const title = cell.title || cell.id.substring(0, 8)
              formattedOutput += `  • ${title}\n`
              formattedOutput += `    ID: ${cell.id}\n`
              if (cell.notebook_item_type_id) {
                formattedOutput += `    Type: ${cell.notebook_item_type_id}\n`
              }
              formattedOutput += `    Assignee: ${cell.assignee_id}\n`
            })
            formattedOutput += '\n'
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `cells_list_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_cells - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('list_cells - Cells list fetched successfully:', { count: data.length })
        return { success: true, data, message: `Retrieved ${data.length} cells` }
      } catch (error) {
        log.error('list_cells - Error:', error)
        throw new Error(`Failed to fetch cells list: ${error.message}`)
      }
    },
    {
      description: 'List cells with RBAC filtering',
      params: [
        { name: 'assignee_id', type: 'string', required: false }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Get Cell
  registerAction(
    'get_cell',
    async (params, ctx) => {
      const { cell_id } = params
      
      if (!cell_id) {
        throw new Error('Required parameter: cell_id')
      }
      
      log.debug('get_cell - Fetching cell details:', { cell_id })
      
      try {
        const response = await apiService.fetch(`/api/cells/${encodeURIComponent(cell_id)}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format cell details for display
        const statusIcon = {
          'pending': '⏳',
          'running': '🔄',
          'completed': '✅',
          'error': '❌'
        }[data.status] || '❓'
        
        let formattedOutput = `🔍 **Cell Details**\n\n`
        formattedOutput += `**ID:** ${data.id}\n`
        formattedOutput += `**Status:** ${statusIcon} ${data.status}\n`
        formattedOutput += `**Title:** ${data.title || '*(No title)*'}\n`
        formattedOutput += `**Assignee:** ${data.assignee_id}\n`
        
        if (data.notebook_item_type_id) {
          formattedOutput += `**Type:** ${data.notebook_item_type_id}\n`
        }
        
        if (data.source_book_id) {
          formattedOutput += `**Source Book:** ${data.source_book_id}\n`
        }
        
        if (data.created_at) {
          formattedOutput += `**Created:** ${data.created_at}\n`
        }
        
        if (data.updated_at) {
          formattedOutput += `**Updated:** ${data.updated_at}\n`
        }
        
        // Content
        const MAX_DISPLAY_LENGTH = 500
        if (data.content) {
          const contentPreview = data.content.length > MAX_DISPLAY_LENGTH 
            ? `${data.content.substring(0, MAX_DISPLAY_LENGTH)}...` 
            : data.content
          formattedOutput += `\n**Content:**\n\`\`\`\n${contentPreview}\n\`\`\`\n`
        }
        
        // Initial Data
        if (data.initial_data && Object.keys(data.initial_data).length > 0) {
          const jsonStr = JSON.stringify(data.initial_data, null, 2)
          const jsonPreview = jsonStr.length > MAX_DISPLAY_LENGTH 
            ? `${jsonStr.substring(0, MAX_DISPLAY_LENGTH)}...` 
            : jsonStr
          formattedOutput += `\n**Initial Data:**\n\`\`\`json\n${jsonPreview}\n\`\`\`\n`
        }
        
        // Fragments
        if (data.fragments && data.fragments.length > 0) {
          formattedOutput += `\n**Fragments:** ${data.fragments.length} fragment(s)\n`
        }
        
        // Refs
        if (data.refs && Object.keys(data.refs).length > 0) {
          formattedOutput += `**Refs:** ${Object.keys(data.refs).length} reference(s)\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `cell_${cell_id.substring(0, 8)}_details.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_cell - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('get_cell - Cell details fetched successfully')
        return { success: true, data, message: 'Cell details retrieved successfully' }
      } catch (error) {
        log.error('get_cell - Error:', error)
        throw new Error(`Failed to fetch cell details: ${error.message}`)
      }
    },
    {
      description: 'Get detailed information about a specific cell',
      params: [
        { name: 'cell_id', type: 'string', required: true }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Execute Cell
  registerAction(
    'execute_cell',
    async (params, ctx) => {
      const { cell_id, parameters } = params
      
      if (!cell_id) {
        throw new Error('Required parameter: cell_id')
      }
      
      log.debug('execute_cell - Executing cell:', { cell_id, parameters })
      
      try {
        const response = await apiService.fetch(`/api/cells/${encodeURIComponent(cell_id)}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ parameters: parameters || {} })
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const statusIcon = {
          'completed': '✅',
          'error': '❌',
          'running': '🔄'
        }[data.status] || '❓'
        
        const formattedOutput = `▶️ **Cell Execution Result**\n\n` +
          `**Cell ID:** ${data.id}\n` +
          `**Status:** ${statusIcon} ${data.status}\n` +
          `**Fragments:** ${data.fragments?.length || 0} fragment(s)\n` +
          `\n✅ Execution completed successfully`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('execute_cell - Cell executed successfully')
        return { success: true, data, message: 'Cell executed successfully' }
      } catch (error) {
        log.error('execute_cell - Error:', error)
        throw new Error(`Failed to execute cell: ${error.message}`)
      }
    },
    {
      description: 'Execute a cell using the pipeline architecture',
      params: [
        { name: 'cell_id', type: 'string', required: true },
        { name: 'parameters', type: 'object', required: false }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Update Cell
  registerAction(
    'update_cell',
    async (params, ctx) => {
      const { cell_id, title, content, status, initial_data, metadata, fragments } = params
      
      if (!cell_id) {
        throw new Error('Required parameter: cell_id')
      }
      
      // Build update payload (only include provided fields)
      const updateData = {}
      if (title !== undefined) updateData.title = title
      if (content !== undefined) updateData.content = content
      if (status !== undefined) updateData.status = status
      if (initial_data !== undefined) updateData.initial_data = initial_data
      if (metadata !== undefined) updateData.metadata = metadata
      if (fragments !== undefined) updateData.fragments = fragments
      
      if (Object.keys(updateData).length === 0) {
        throw new Error('At least one field must be provided for update')
      }
      
      log.debug('update_cell - Updating cell:', { cell_id, fields: Object.keys(updateData) })
      
      try {
        const response = await apiService.fetch(`/api/cells/${encodeURIComponent(cell_id)}/update`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updateData)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `✏️ **Cell Updated Successfully**\n\n` +
          `**Cell ID:** ${data.id}\n` +
          `**Updated Fields:** ${Object.keys(updateData).join(', ')}\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Update completed`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('update_cell - Cell updated successfully')
        return { success: true, data, message: 'Cell updated successfully' }
      } catch (error) {
        log.error('update_cell - Error:', error)
        throw new Error(`Failed to update cell: ${error.message}`)
      }
    },
    {
      description: 'Update cell properties',
      params: [
        { name: 'cell_id', type: 'string', required: true },
        { name: 'title', type: 'string', required: false },
        { name: 'content', type: 'string', required: false },
        { name: 'status', type: 'string', required: false },
        { name: 'initial_data', type: 'object', required: false },
        { name: 'metadata', type: 'object', required: false },
        { name: 'fragments', type: 'array', required: false }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Delete Cell
  registerAction(
    'delete_cell',
    async (params, ctx) => {
      const { cell_id } = params
      
      if (!cell_id) {
        throw new Error('Required parameter: cell_id')
      }
      
      log.debug('delete_cell - Deleting cell:', { cell_id })
      
      try {
        const response = await apiService.fetch(`/api/cells/${encodeURIComponent(cell_id)}`, {
          method: 'DELETE'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const formattedOutput = `🗑️ **Cell Deleted**\n\n` +
          `**Cell ID:** ${cell_id}\n` +
          `\n✅ Cell permanently removed from database`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('delete_cell - Cell deleted successfully')
        return { success: true, message: 'Cell deleted successfully' }
      } catch (error) {
        log.error('delete_cell - Error:', error)
        throw new Error(`Failed to delete cell: ${error.message}`)
      }
    },
    {
      description: 'Delete a cell permanently',
      params: [
        { name: 'cell_id', type: 'string', required: true }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: List Notebook Item Types
  registerAction(
    'list_notebook_item_types',
    async (params, ctx) => {
      log.debug('list_notebook_item_types - Fetching types')
      
      try {
        const response = await apiService.fetch('/api/cells/types/list')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        let formattedOutput = `📚 **Notebook Item Types** (${data.length} type${data.length !== 1 ? 's' : ''})\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No types found*'
        } else {
          data.forEach(type => {
            formattedOutput += `**${type.name}**\n`
            formattedOutput += `  ID: ${type.id}\n`
            if (type.description) {
              formattedOutput += `  Description: ${type.description}\n`
            }
            formattedOutput += `  Override Refs: ${type.allow_instance_override_refs ? '✓' : '✗'}\n`
            formattedOutput += '\n'
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `notebook_types_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_notebook_item_types - Results attached:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('list_notebook_item_types - Types fetched successfully:', { count: data.length })
        return { success: true, data, message: `Retrieved ${data.length} types` }
      } catch (error) {
        log.error('list_notebook_item_types - Error:', error)
        throw new Error(`Failed to fetch types: ${error.message}`)
      }
    },
    {
      description: 'List available notebook item types',
      params: [],
      category: 'cells',
      available: true
    }
  )
  
  // ========================================
  // ISSUES ACTIONS: Backend-only RBAC actions
  // ========================================
  
  // Action: Trigger Manual Ingest
  registerAction(
    'trigger_manual_ingest',
    async (params, ctx) => {
      const { source_dir, dry_run } = params
      
      log.debug('trigger_manual_ingest - Triggering ingest:', { source_dir, dry_run })
      
      try {
        const response = await apiService.fetch('/api/issues/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_dir: source_dir || null,
            dry_run: dry_run || false
          })
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `📥 **Manual Ingest Triggered**\n\n` +
          `**Status:** ${data.status}\n` +
          `${data.message ? `**Message:** ${data.message}\n` : ''}` +
          `${source_dir ? `**Source:** ${source_dir}\n` : ''}` +
          `${dry_run ? `**Mode:** Dry Run (no actual ingestion)\n` : ''}` +
          `\n✅ Ingestion process started`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('trigger_manual_ingest - Ingest triggered successfully')
        return { success: true, data, message: 'Ingest triggered successfully' }
      } catch (error) {
        log.error('trigger_manual_ingest - Error:', error)
        throw new Error(`Failed to trigger ingest: ${error.message}`)
      }
    },
    {
      description: 'Trigger manual ingestion of documents',
      params: [
        { name: 'source_dir', type: 'string', required: false },
        { name: 'dry_run', type: 'boolean', required: false }
      ],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Trigger Manual Processing
  registerAction(
    'trigger_manual_processing',
    async (params, ctx) => {
      log.debug('trigger_manual_processing - Triggering processing')
      
      try {
        const response = await apiService.fetch('/api/issues/process', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `⚡ **Manual Processing Triggered**\n\n` +
          `**Status:** ${data.status}\n` +
          `**Processed:** ${data.processed} cell(s)\n` +
          `\n✅ Processing completed`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('trigger_manual_processing - Processing triggered successfully')
        return { success: true, data, message: 'Processing triggered successfully' }
      } catch (error) {
        log.error('trigger_manual_processing - Error:', error)
        throw new Error(`Failed to trigger processing: ${error.message}`)
      }
    },
    {
      description: 'Trigger manual processing of pending cells',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Start Automatic Monitoring
  registerAction(
    'start_automatic_monitoring',
    async (params, ctx) => {
      log.debug('start_automatic_monitoring - Starting monitoring')
      
      try {
        const response = await apiService.fetch('/api/issues/monitoring/start', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `▶️ **Automatic Monitoring Started**\n\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Background monitoring loop is now active`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('start_automatic_monitoring - Monitoring started')
        return { success: true, data, message: 'Monitoring started successfully' }
      } catch (error) {
        log.error('start_automatic_monitoring - Error:', error)
        throw new Error(`Failed to start monitoring: ${error.message}`)
      }
    },
    {
      description: 'Start automatic monitoring loop',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Stop Automatic Monitoring
  registerAction(
    'stop_automatic_monitoring',
    async (params, ctx) => {
      log.debug('stop_automatic_monitoring - Stopping monitoring')
      
      try {
        const response = await apiService.fetch('/api/issues/monitoring/stop', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `⏹️ **Automatic Monitoring Stopped**\n\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Background monitoring loop has been stopped`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('stop_automatic_monitoring - Monitoring stopped')
        return { success: true, data, message: 'Monitoring stopped successfully' }
      } catch (error) {
        log.error('stop_automatic_monitoring - Error:', error)
        throw new Error(`Failed to stop monitoring: ${error.message}`)
      }
    },
    {
      description: 'Stop automatic monitoring loop',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Pause Queue Processing
  registerAction(
    'pause_queue_processing',
    async (params, ctx) => {
      log.debug('pause_queue_processing - Pausing processing')
      
      try {
        const response = await apiService.fetch('/api/issues/processing/pause', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `⏸️ **Queue Processing Paused**\n\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Cell processing is now paused (monitoring continues)`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('pause_queue_processing - Processing paused')
        return { success: true, data, message: 'Processing paused successfully' }
      } catch (error) {
        log.error('pause_queue_processing - Error:', error)
        throw new Error(`Failed to pause processing: ${error.message}`)
      }
    },
    {
      description: 'Pause queue processing',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Resume Queue Processing
  registerAction(
    'resume_queue_processing',
    async (params, ctx) => {
      log.debug('resume_queue_processing - Resuming processing')
      
      try {
        const response = await apiService.fetch('/api/issues/processing/resume', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `▶️ **Queue Processing Resumed**\n\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Cell processing has been resumed`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('resume_queue_processing - Processing resumed')
        return { success: true, data, message: 'Processing resumed successfully' }
      } catch (error) {
        log.error('resume_queue_processing - Error:', error)
        throw new Error(`Failed to resume processing: ${error.message}`)
      }
    },
    {
      description: 'Resume queue processing',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  log.debug(`Initialized ${actionRegistry.value.size} default actions`)
}

/**
 * Exporta definições de ações para o backend
 * Permite que o AgenteLab saiba quais ações estão disponíveis
 * @returns {Array} Lista de definições de ações
 */
export function exportActionDefinitions() {
  return Array.from(actionRegistry.value.values()).map(action => ({
    name: action.name,
    description: action.metadata.description,
    params: action.metadata.params,
    category: action.metadata.category,
    example: createActionURL(
      action.name,
      Object.fromEntries(
        action.metadata.params
          .filter(p => p.required)
          .map(p => [p.name, `<${p.name}>`])
      )
    )
  }))
}
