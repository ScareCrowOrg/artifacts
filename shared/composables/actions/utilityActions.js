/**
 * Utility Actions
 * 
 * General utility actions: copy_to_clipboard, open_docs, navigate, create_cell
 */

import { createLogger } from '@/utils/logger'

const log = createLogger('action:utility')

/**
 * Register utility actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerUtilityActions(registerAction) {
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
}
