/**
 * Traces Service
 * Handles API communication for conversation trace retrieval and analysis
 * 
 * Technical naming: All functions and variables in English
 */

import { ENDPOINTS } from '@/config/endpoints.js'
import apiService from '@/services/apiService.js'

interface TraceFragment {
  timestamp: string
  stage: string
  stageLabel: string
  stageIcon: string
  data: any
  conversationId: string
}

interface RawFragment {
  timestamp: string
  stage: string
  data: any
  conversation_id: string
}

interface RecentTracesParams {
  limit?: number
  offset?: number
}

interface RecentTracesResponse {
  count: number
  traces: any[]
}

/**
 * Fetch conversation trace data by conversation ID
 * Retrieves complete trace with all fragments from backend API
 * 
 * @param conversationId - Unique conversation identifier
 * @returns Trace data with fragments
 * @throws Error if API request fails
 */
export async function fetchTraceByConversationId(conversationId: string): Promise<any> {
  if (!conversationId) {
    throw new Error('conversationId is required')
  }

  const url = `${ENDPOINTS.tracesBase}/conversation/${conversationId}`
  const response = await apiService.fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`No trace found for conversation: ${conversationId}`)
    } else if (response.status === 403) {
      throw new Error('Not authorized to view this trace')
    }
    throw new Error(`API error: ${response.status}`)
  }

  return await response.json()
}

/**
 * Fetch recent conversation traces for current user
 * Returns paginated list of trace summaries
 * 
 * @param params - Query parameters
 * @returns Object with count and traces array
 * @throws Error if API request fails
 */
export async function fetchRecentTraces({ limit = 10, offset = 0 }: RecentTracesParams = {}): Promise<RecentTracesResponse> {
  const url = `${ENDPOINTS.tracesBase}/recent?limit=${limit}&offset=${offset}`
  const response = await apiService.fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch recent traces: ${response.status}`)
  }

  return await response.json()
}

/**
 * Format trace fragment for display
 * Converts fragment data to human-readable format
 * 
 * @param fragment - Raw fragment from API
 * @returns Formatted fragment with display-friendly fields
 */
export function formatTraceFragment(fragment: RawFragment | null): TraceFragment | null {
  if (!fragment) {
    return null
  }

  return {
    timestamp: fragment.timestamp,
    stage: fragment.stage,
    stageLabel: getStageLabel(fragment.stage),
    stageIcon: getStageIcon(fragment.stage),
    data: fragment.data,
    conversationId: fragment.conversation_id,
  }
}

/**
 * Get human-readable label for trace stage
 * 
 * @param stage - Stage identifier
 * @returns Display label
 */
export function getStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    initial_prompt: 'Prompt Inicial',
    file_upload: 'Upload de Arquivos',
    history_processed: 'Histórico Processado',
    query_expanded: 'Expansão de Query',
    rag_retrieval: 'Busca RAG',
    rag_post_processing: 'Pós-processamento RAG',
    context_assembled: 'Contexto Montado',
    final_llm_call: 'Chamada LLM Final',
    llm_response: 'Resposta LLM',
  }
  return labels[stage] || stage
}

/**
 * Get icon/emoji for trace stage
 * 
 * @param stage - Stage identifier
 * @returns Icon/emoji character
 */
export function getStageIcon(stage: string): string {
  const icons: Record<string, string> = {
    initial_prompt: '💬',
    file_upload: '📎',
    history_processed: '📚',
    query_expanded: '🔍',
    rag_retrieval: '🎯',
    rag_post_processing: '⚙️',
    context_assembled: '📦',
    final_llm_call: '🤖',
    llm_response: '💡',
  }
  return icons[stage] || '📋'
}

/**
 * Get color class for trace stage
 * Returns Tailwind CSS color utility class
 * 
 * @param stage - Stage identifier
 * @returns Tailwind color class
 */
export function getStageColor(stage: string): string {
  const colors: Record<string, string> = {
    initial_prompt: 'text-blue-600',
    file_upload: 'text-purple-600',
    history_processed: 'text-green-600',
    query_expanded: 'text-orange-600',
    rag_retrieval: 'text-pink-600',
    rag_post_processing: 'text-yellow-600',
    context_assembled: 'text-indigo-600',
    final_llm_call: 'text-red-600',
    llm_response: 'text-teal-600',
  }
  return colors[stage] || 'text-gray-600'
}

export default {
  fetchTraceByConversationId,
  fetchRecentTraces,
  formatTraceFragment,
  getStageLabel,
  getStageIcon,
  getStageColor,
}
