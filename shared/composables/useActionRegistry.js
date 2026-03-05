/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-22",
 *   "console_calls_found": 55,
 *   "console_calls_migrated": 55,
 *   "migration_rate": 100,
 *   "logger_namespace": "action:registry",
 *   "validation_status": "excellent",
 *   "modularized": true,
 *   "modularization_date": "2025-12-26"
 *   }
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
 * 
 * This file has been modularized to comply with RULESET.md (500-line limit).
 * Action handlers are organized in separate files under actions/ subdirectory.
 * 
 * ⚠️ INTENTIONAL SINGLETON PATTERN (Issue #1400)
 * 
 * This composable intentionally uses module-level state for global action registry.
 * Action handlers are registered once and shared across all components for
 * consistent action link execution from chat responses.
 * 
 * Pattern: Global registry of action handlers
 * 
 * DO NOT migrate to Factory-per-ID pattern - action handlers are global by design.
 */

import { ref } from 'vue'
import { createLogger } from '@/utils/logger'

// Import modular action registrations
import { registerRuntimeActions } from './actions/runtimeActions'
import { registerProposalActions } from './actions/proposalActions'
import { registerUtilityActions } from './actions/utilityActions'
import { registerDiscoveryActions } from './actions/discoveryActions'
import { registerGitHubActions } from './actions/githubActions'
import { registerCellActions } from './actions/cellActions'
import { registerIssuesActions } from './actions/issuesActions'
import { registerBooksActions } from './actions/booksActions'
import { registerRolesActions } from './actions/rolesActions'
import { registerAIModelsActions } from './actions/aiModelsActions'
import { registerUsersActions } from './actions/usersActions'
import { registerAuditActions } from './actions/auditActions'
import { registerTracesActions } from './actions/tracesActions'
import { registerSessionsActions } from './actions/sessionsActions'
import { registerConfigActions } from './actions/configActions'
import { registerServicesActions } from './actions/servicesActions'
import { registerSystemActions } from './actions/systemActions'

const log = createLogger('action:registry')

// Registry de ações disponíveis
const actionRegistry = ref(new Map())

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
// INITIALIZE DEFAULT ACTIONS
// ========================================

/**
 * Inicializa ações padrão do sistema
 * @param {Object} context - Contexto global (stores, router)
 */
export function initializeDefaultActions(context) {
  // Register all action categories
  registerRuntimeActions(registerAction)
  registerProposalActions(registerAction)
  registerUtilityActions(registerAction)
  registerDiscoveryActions(registerAction)
  registerGitHubActions(registerAction)
  registerCellActions(registerAction)
  registerIssuesActions(registerAction)
  registerBooksActions(registerAction)
  registerRolesActions(registerAction)
  registerAIModelsActions(registerAction)
  registerUsersActions(registerAction)
  registerAuditActions(registerAction)
  registerTracesActions(registerAction)
  registerSessionsActions(registerAction)
  registerConfigActions(registerAction)
  registerServicesActions(registerAction)
  registerSystemActions(registerAction)
  
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
