/**
 * Proposal Actions
 * 
 * Actions for proposing file modifications: propose_file_update, propose_file_creation
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'
import { safeDecodeURIComponent } from './utils'

const log = createLogger('action:proposal')

/**
 * Register proposal actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerProposalActions(registerAction) {
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
}
