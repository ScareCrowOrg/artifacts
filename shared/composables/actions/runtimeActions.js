/**
 * Runtime Actions
 * 
 * Actions for runtime file operations: grep, find, read_file
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'
import {
  formatGrepResults,
  formatFindResults,
  truncateIfNeeded,
  shouldUseAttachment,
  generateAttachmentFilename
} from './utils'

const log = createLogger('action:runtime')

/**
 * Register runtime actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerRuntimeActions(registerAction) {
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
}
