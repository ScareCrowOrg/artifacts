/**
 * Dual API Configuration for ScareVerse Frontend
 * 
 * Phase 0: Frontend knows two API bases:
 * - CentralHub: Centralized infrastructure (via Nginx in Kubernetes cluster)
 * - LocalRunner: Local-first execution (ScareRunner direct connection)
 * 
 * Architecture:
 * - CentralHub handles: Authentication, System config, User management
 * - LocalRunner handles: Cell execution, AI processing, Local artifacts
 */

// Get CentralHub base URL (cluster infrastructure via Nginx)
const getCentralHubBase = () => {
  // Check for explicit configuration
  if (window.VITE_CENTRAL_HUB_URL) {
    return window.VITE_CENTRAL_HUB_URL
  }

  // Check for environment variable (Vite specific)
  if (import.meta.env.VITE_CENTRAL_HUB_URL) {
    return import.meta.env.VITE_CENTRAL_HUB_URL
  }

  // Fallback to Nginx proxy (standard cluster setup)
  return 'http://localhost:8000'
}

// Get LocalRunner base URL (local-first execution)
const getLocalRunnerBase = () => {
  // Check for explicit configuration
  if (window.VITE_LOCAL_RUNNER_URL) {
    return window.VITE_LOCAL_RUNNER_URL
  }

  // Check for environment variable (Vite specific)
  if (import.meta.env.VITE_LOCAL_RUNNER_URL) {
    return import.meta.env.VITE_LOCAL_RUNNER_URL
  }

  // Fallback to ScareRunner default port
  return 'http://localhost:5050'
}

export const CENTRAL_HUB_BASE = getCentralHubBase()
export const LOCAL_RUNNER_BASE = getLocalRunnerBase()

// Legacy support - defaults to CentralHub for backward compatibility
export const API_BASE = CENTRAL_HUB_BASE
export const API_BASE_URL = API_BASE

/**
 * API Base Selection Guide:
 * 
 * Use CENTRAL_HUB_BASE for:
 * - Authentication (login, logout, tokens)
 * - User management (create, update, permissions)
 * - System configuration (global settings)
 * - Cluster-wide operations
 * 
 * Use LOCAL_RUNNER_BASE for:
 * - Cell execution (run cells, get results)
 * - AI operations (Gemini, OpenAI, local models)
 * - Artifact access (load cells, books)
 * - Local-first operations that work offline
 * 
 * Example:
 * ```javascript
 * // System operation - use CentralHub
 * fetch(`${CENTRAL_HUB_BASE}/api/auth/login`, {...})
 * 
 * // Cell execution - use LocalRunner
 * fetch(`${LOCAL_RUNNER_BASE}/api/cells/${cellId}/execute`, {...})
 * 
 * // Artifact access - use LocalRunner
 * fetch(`${LOCAL_RUNNER_BASE}/local/canonical/cell_types/...`, {...})
 * ```
 */

console.log('🌐 API Configuration:')
console.log('  CentralHub (cluster):', CENTRAL_HUB_BASE)
console.log('  LocalRunner (local):', LOCAL_RUNNER_BASE)
console.log('  Legacy API_BASE:', API_BASE)
